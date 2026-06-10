import os
import math
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_OL = _load('wdth_offset', 'wdth_offset.py')

UPM = 2048.0
N_SCAN = 25
SCAN_LO = 0.06
SCAN_HI = 0.94
WG_MIN = 20.0
WG_MAX = 500.0
MIN_RUN = max(24.0, 0.012 * UPM)
MIN_STEM = 0.025 * UPM
MAX_STEM = 0.130 * UPM
STEM_PRIOR = 0.083 * UPM
MIN_CLUSTER_SUPPORT = 2
MODE_BIN = 8.0
MODE_BAND = 10.0
MODE_NEIGHBORS = 1
MIN_MODE_SUPPORT = 3
SUPPORT_TIE_SCANLINES = 2
SUPPORT_TIE_RATIO = 0.88

_FALLBACK = {'stem': None}


def _fracs():
    step = (SCAN_HI - SCAN_LO) / (N_SCAN - 1)
    return [SCAN_LO + i * step for i in range(N_SCAN)]


def _scan_runs(polys, axis_val, horizontal=True):
    crossings = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            a1, b1 = (p1[1], p1[0]) if horizontal else (p1[0], p1[1])
            a2, b2 = (p2[1], p2[0]) if horizontal else (p2[0], p2[1])
            if (a1 <= axis_val < a2) or (a2 <= axis_val < a1):
                t = (axis_val - a1) / (a2 - a1)
                crossings.append(b1 + t * (b2 - b1))
    crossings.sort()
    return [crossings[i + 1] - crossings[i] for i in range(0, len(crossings) - 1, 2)]


def _median(vals):
    s = sorted(vals)
    return s[len(s) // 2]


def _cluster(widths):
    cand = sorted(w for w in widths if w >= MIN_RUN)
    if not cand:
        return []
    clusters = []
    cur = [cand[0]]
    for w in cand[1:]:
        if w - cur[-1] > max(32.0, 0.22 * cur[-1]):
            clusters.append(cur)
            cur = [w]
        else:
            cur.append(w)
    clusters.append(cur)
    return clusters


def _select(clusters):
    candidates = [c for c in clusters if MIN_STEM <= _median(c) <= MAX_STEM]
    if not candidates:
        return None
    best = min(candidates, key=lambda c: (-len(c), abs(math.log(_median(c) / STEM_PRIOR)), _median(c)))
    return _median(best)


def _select_supported_mode(samples):
    bins = {}
    scans = {}
    for si, w in samples:
        if not (MIN_STEM <= w <= MAX_STEM):
            continue
        b = int(math.floor(w / MODE_BIN + 0.5))
        bins.setdefault(b, []).append(w)
        scans.setdefault(b, set()).add(si)
    if not bins:
        return None
    candidates = []
    for b in bins:
        support_scans = set()
        local_widths = []
        for nb in range(b - MODE_NEIGHBORS, b + MODE_NEIGHBORS + 1):
            support_scans.update(scans.get(nb, ()))
            local_widths.extend(bins.get(nb, ()))
        support = len(support_scans)
        if support < MIN_MODE_SUPPORT:
            continue
        center = b * MODE_BIN
        band_widths = [w for w in local_widths if abs(w - center) <= MODE_BAND]
        value = _median(band_widths or bins[b])
        if MIN_STEM <= value <= MAX_STEM:
            candidates.append((support, value))
    if not candidates:
        return None
    max_support = max(s for s, _ in candidates)
    support_cut = max(MIN_MODE_SUPPORT, max_support - SUPPORT_TIE_SCANLINES,
                      math.ceil(max_support * SUPPORT_TIE_RATIO))
    strong = [(s, v) for s, v in candidates if s >= support_cut]
    support, value = min(strong, key=lambda sv: (abs(math.log(sv[1] / STEM_PRIOR)), -sv[0], sv[1]))
    return value


def measure_stem(glyf, gn, flatness=0.6):
    polys = _OL.flatten_contours(glyf, gn, flatness)
    if not polys:
        return None
    xs = [x for p in polys for x, y in p]
    ys = [y for p in polys for x, y in p]
    if not ys:
        return None
    ymin, ymax = min(ys), max(ys)
    xmin, xmax = min(xs), max(xs)
    yspan = ymax - ymin
    xspan = xmax - xmin
    if yspan < 1.0:
        return None

    h_widths = []
    h_samples = []
    for i, r in enumerate(_fracs()):
        for w in _scan_runs(polys, ymin + yspan * r, horizontal=True):
            if w > 0:
                h_widths.append(w)
                h_samples.append((i, w))
    est = _select_supported_mode(h_samples)
    if est is None:
        est = _select(_cluster(h_widths))
    if est is not None:
        return est

    if xspan >= 1.0:
        v_widths = []
        v_samples = []
        for i, r in enumerate(_fracs()):
            for w in _scan_runs(polys, xmin + xspan * r, horizontal=False):
                if w > 0:
                    v_widths.append(w)
                    v_samples.append((i, w))
        est = _select_supported_mode(v_samples)
        if est is None:
            est = _select(_cluster(v_widths))
        if est is not None:
            return est

    return _FALLBACK['stem']


def set_fallback_stem(value):
    _FALLBACK['stem'] = value


def compute_fallback_stem(glyf, cmap):
    probes = ['ㅣ', '한', 'n', 'H', 'l', 'I']
    vals = []
    for ch in probes:
        gn = cmap.get(ord(ch))
        if gn is None:
            continue
        g = glyf[gn]
        if not hasattr(g, 'numberOfContours') or g.numberOfContours <= 0:
            continue
        wg = measure_stem(glyf, gn)
        if wg is not None and WG_MIN <= wg <= WG_MAX:
            vals.append(wg)
    if vals:
        return _median(vals)
    return 160.0


def get_stem_width(glyf, gn, is_cjk_glyph, medians):
    wg = measure_stem(glyf, gn)
    if wg is None or wg < WG_MIN or wg > WG_MAX:
        cls = 'cjk' if is_cjk_glyph else 'latin'
        return medians[cls], False
    return wg, True


def measure_worst_stem(glyf, gn, flatness=0.6, support_frac=0.5):
    # Min width among vertical stems that persist across >=support_frac of scanlines.
    # Used by the condense solver so multi-stem glyphs (m, q, ...) don't satisfy a
    # single-mode target while their sibling stems collapse. Returns None if no
    # reliable stem cluster is found (caller falls back to single-stem measure).
    polys = _OL.flatten_contours(glyf, gn, flatness)
    if not polys:
        return None
    ally = [y for p in polys for x, y in p]
    if not ally:
        return None
    ylo, yhi = min(ally), max(ally)
    ysp = yhi - ylo
    if ysp < 1.0:
        return None
    nscan = 20
    fr = [0.15 + 0.7 * i / (nscan - 1) for i in range(nscan)]
    clusters = []
    for r in fr:
        for w, xc in _scan_runs_xc(polys, ylo + ysp * r):
            if not (MIN_STEM <= w <= MAX_STEM):
                continue
            placed = False
            for cl in clusters:
                if abs(cl['xc'] - xc) < 60.0:
                    cl['ws'].append(w)
                    cl['xc'] = (cl['xc'] * cl['n'] + xc) / (cl['n'] + 1)
                    cl['n'] += 1
                    placed = True
                    break
            if not placed:
                clusters.append({'xc': xc, 'ws': [w], 'n': 1})
    cand = [_median(cl['ws']) for cl in clusters if cl['n'] >= nscan * support_frac]
    return min(cand) if cand else None


def _scan_runs_xc(polys, axis_val):
    crossings = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            a1, b1 = p1[1], p1[0]
            a2, b2 = p2[1], p2[0]
            if (a1 <= axis_val < a2) or (a2 <= axis_val < a1):
                t = (axis_val - a1) / (a2 - a1)
                crossings.append(b1 + t * (b2 - b1))
    crossings.sort()
    out = []
    for i in range(0, len(crossings) - 1, 2):
        out.append((crossings[i + 1] - crossings[i], (crossings[i] + crossings[i + 1]) / 2.0))
    return out


def compute_class_medians(glyf, glyph_order, cjk_set):
    cjk_vals = []
    latin_vals = []
    for gn in glyph_order:
        g = glyf[gn]
        g.expand(glyf)
        if not hasattr(g, 'numberOfContours') or g.numberOfContours <= 0:
            continue
        wg = measure_stem(glyf, gn)
        if wg is None or wg < WG_MIN or wg > WG_MAX:
            continue
        if gn in cjk_set:
            cjk_vals.append(wg)
        else:
            latin_vals.append(wg)

    def med(vals, fallback):
        if not vals:
            return fallback
        vals.sort()
        return vals[len(vals) // 2]

    return {'cjk': med(cjk_vals, 148.0), 'latin': med(latin_vals, 133.0)}
