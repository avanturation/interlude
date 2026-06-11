"""Add a wdth (Width) variable axis to the merged Interlude VF.

Runs after build-full.py. For every glyph it synthesises point-preserving
horizontal displacement deltas (stem-preserving condensation/expansion via the
displacement field new_x = s*x + delta*nx, delta = W*(1-s)/2) and injects them
as gvar TupleVariations on the wdth axis. Outlines keep their exact point count
so the master/delta topology stays interpolable. A per-glyph self-intersection
guard reduces the displacement factor when condensation would fold an outline.
"""
import sys
import os
import time
import importlib.util
from multiprocessing import Pool, cpu_count

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.ttLib.tables import otTables
from fontTools.otlLib.builder import buildStatTable

WDTH_MIN = 75.0
WDTH_DEFAULT = 100.0
WDTH_MAX = 125.0
S_CONDENSE = 0.75
S_EXPAND = 1.25
# Round latin glyphs (o c e a b d p q g ...) condense their bowl bodies to a higher
# scale than straight-stem glyphs at the heavy+condensed corner. A pure s=0.75 body
# is too narrow to hold both thick bowl walls and an open counter, so the old
# counter-opening correction (mult*0.82) thinned the walls ~25% below the straight
# stems (Black-Condensed "Typeface" read as uneven). SF Pro instead condenses round
# glyphs less; matching that with s=0.86 (full wall restoration) keeps walls at the
# straight-stem weight AND the counter open, at the same advance width.
S_ROUND_CONDENSE = 0.86
# Mixed glyphs carry both a straight stem and a closed bowl joined on one contour, so
# the counter-opening normal push that cleanly thickens symmetric bowls (o e 0) flips
# direction sharply at the stem/bowl junction, spiking the edge's second derivative (6
# hits 151 vs o's 8) and reading as a bump-next-to-dent or a lopsided counter. b p q are
# mirror-images of d and share its junction, so they need the same attenuation. Dropping
# the push to 0.90 cuts those spikes ~4x (6: 151->37, g: 94->0, d: 118->20) and brings
# b/p/q from a 12.6u push down to d's 3.6u, while symmetric bowls keep the full push.
S_MIXED_OPENING = 0.90
_MIXED_GLYPHS = set('6cdgsabpq')
# wdth axis: min75/def100/max125. Single master per side: wdth=75 (s=0.75) and
# wdth=125 (s=1.25), both at normalized -1.0/+1.0. wdth=150 was removed because
# expansion to s=1.5 broke diagonals (X strokes not meeting, x/g/m/y distortion).

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_cjk(cp):
    return cp is not None and (
        0xAC00 <= cp <= 0xD7A3 or 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF
        or 0x3040 <= cp <= 0x30FF or 0x3000 <= cp <= 0x303F or 0xFF00 <= cp <= 0xFFEF
    )


def is_latin_base(cp):
    return cp is not None and (
        0x0041 <= cp <= 0x005A or 0x0061 <= cp <= 0x007A or 0x00C0 <= cp <= 0x024F
    )


_W = {}


def _init(src, medians):
    _W['DP'] = _load('wdth_displace', 'wdth_displace.py')
    _W['ST'] = _load('wdth_stems', 'wdth_stems.py')
    _W['MU'] = _load('wdth_multipliers', 'wdth_multipliers.py')
    _W['ST'].set_fallback_stem(medians.get('fallback'))
    f = TTFont(src)
    _W['glyf'] = f['glyf']
    _W['hmtx'] = f['hmtx']
    _W['medians'] = medians


def _work(args):
    chunk, scale = args
    DP = _W['DP']
    ST = _W['ST']
    MU = _W['MU']
    glyf = _W['glyf']
    hmtx = _W['hmtx']
    medians = _W['medians']
    out = {}
    for gn, cp in chunk:
        g = glyf[gn]
        g.expand(glyf)
        if not hasattr(g, 'numberOfContours') or g.numberOfContours <= 0:
            continue
        cjk = is_cjk(cp)
        wg, reliable = ST.get_stem_width(glyf, gn, cjk, medians)
        if cjk and reliable:
            mult = MU.cjk_stem_multiplier(scale, wg)
        else:
            mult = MU.latin_stem_multiplier(scale)
        res = DP.displace_v2(glyf, gn, scale, wg, mult, allow_anchor=False, allow_diag=True)
        if res is None:
            continue
        coords, ends, flags, base, seff = res
        aw, lsb = hmtx[gn]
        bxs = [x for x, y in base]
        rsb = aw - lsb - (max(bxs) - min(bxs))
        deltas, aw1 = DP.finalize_metrics(coords, base, lsb, rsb, aw, scale)
        out[gn] = (deltas, seff)
    return out


def _add_axis_and_instances(f):
    from fontTools.ttLib.tables._f_v_a_r import NamedInstance
    fvar = f['fvar']
    name = f['name']
    if not any(a.axisTag == 'wdth' for a in fvar.axes):
        ax = Axis()
        ax.axisTag = 'wdth'
        ax.minValue = WDTH_MIN
        ax.defaultValue = WDTH_DEFAULT
        ax.maxValue = WDTH_MAX
        ax.axisNameID = name.addName('Width')
        fvar.axes.append(ax)
    for inst in fvar.instances:
        inst.coordinates.setdefault('wdth', WDTH_DEFAULT)
    base = [i for i in fvar.instances if i.coordinates.get('wdth') == WDTH_DEFAULT]
    for inst in base:
        if inst.postscriptNameID in (None, 0xFFFF):
            weight = name.getDebugName(inst.subfamilyNameID)
            ps_weight = '' if weight == 'Regular' else weight
            inst.postscriptNameID = name.addName(f'Interlude-{ps_weight}' if ps_weight else 'Interlude-Regular')
    added = []
    for prefix, wd in (('Condensed', WDTH_MIN), ('Expanded', WDTH_MAX)):
        for inst in base:
            weight = name.getDebugName(inst.subfamilyNameID)
            ni = NamedInstance()
            ni.coordinates = dict(inst.coordinates)
            ni.coordinates['wdth'] = wd
            ni.subfamilyNameID = name.addName(f'{prefix} {weight}')
            ps_weight = '' if weight == 'Regular' else weight
            ps_name = f'Interlude-{prefix}{ps_weight}'
            ni.postscriptNameID = name.addName(ps_name)
            added.append(ni)
    fvar.instances.extend(added)


def _sync_variation_tables(f):
    n_axes = len(f['fvar'].axes)
    if 'avar' in f:
        seg = f['avar'].segments
        if seg.get('wdth') in (None, {}):
            seg['wdth'] = {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0}
    for tag in ('MVAR', 'HVAR', 'VVAR', 'GDEF'):
        if tag not in f:
            continue
        vs = getattr(f[tag].table, 'VarStore', None)
        if vs is None:
            continue
        rl = vs.VarRegionList
        if rl.RegionAxisCount >= n_axes:
            continue
        for region in rl.Region:
            while len(region.VarRegionAxis) < n_axes:
                a = otTables.VarRegionAxis()
                a.StartCoord = 0
                a.PeakCoord = 0
                a.EndCoord = 0
                region.VarRegionAxis.append(a)
        rl.RegionAxisCount = n_axes


def _strip_mac_names(f):
    f['name'].names = [r for r in f['name'].names if r.platformID != 1]



def _compute(src, scale, medians):
    f = TTFont(src)
    glyf = f['glyf']
    cmap = f.getBestCmap()
    rev = {}
    for cp, gn in cmap.items():
        rev.setdefault(gn, cp)
    jobs = []
    for gn in f.getGlyphOrder():
        g = glyf[gn]
        g.expand(glyf)
        if not hasattr(g, 'numberOfContours') or g.numberOfContours <= 0:
            continue
        jobs.append((gn, rev.get(gn)))
    nproc = min(cpu_count(), 14)
    size = 64
    chunks = [(jobs[i:i + size], scale) for i in range(0, len(jobs), size)]
    results = {}
    with Pool(nproc, initializer=_init, initargs=(src, medians)) as pool:
        for r in pool.imap_unordered(_work, chunks):
            results.update(r)
    return results


def _compute_medians(src):
    ST = _load('wdth_stems', 'wdth_stems.py')
    f = TTFont(src)
    glyf = f['glyf']
    cmap = f.getBestCmap()
    rev = {}
    for cp, gn in cmap.items():
        rev.setdefault(gn, cp)
    fallback = ST.compute_fallback_stem(glyf, cmap)
    ST.set_fallback_stem(fallback)
    cjk_set = {gn for gn in f.getGlyphOrder() if is_cjk(rev.get(gn))}
    order = f.getGlyphOrder()
    cjk_jobs = [gn for gn in order if gn in cjk_set]
    latin_jobs = [gn for gn in order if gn not in cjk_set]
    sample = cjk_jobs[::max(1, len(cjk_jobs) // 600)] + latin_jobs[::max(1, len(latin_jobs) // 600)]
    sset = set(sample)
    medians = ST.compute_class_medians(glyf, [g for g in order if g in sset], cjk_set)
    medians['fallback'] = fallback
    return medians


def _varied_center(glyf, gname, width_deltas):
    g = glyf[gname]
    g.expand(glyf)
    if g.numberOfContours is None or g.numberOfContours == 0:
        return None
    if g.numberOfContours < 0:
        cs = []
        for c in g.components:
            cc = _varied_center(glyf, c.glyphName, width_deltas)
            if cc is not None:
                cs.append(cc + getattr(c, 'x', 0))
        return sum(cs) / len(cs) if cs else None
    xs = [x for x, y in g.coordinates]
    if not xs:
        return None
    d = width_deltas.get(gname)
    if d is not None:
        pd = d[0]
        n = min(len(xs), len(pd))
        vx = [xs[i] + pd[i][0] for i in range(n)]
    else:
        vx = xs
    return (min(vx) + max(vx)) / 2.0


def _composite_deltas(comps, aw, lsb, rsb, scale, glyf=None, width_deltas=None):
    MU = _load('wdth_multipliers', 'wdth_multipliers.py')
    lsb1 = MU.scale_sidebearing(lsb, scale)
    rsb1 = MU.scale_sidebearing(rsb, scale)
    body = aw - lsb - rsb
    aw1 = round(lsb1 + body * scale + rsb1)

    deltas = []
    if glyf is not None and width_deltas is not None and len(comps) >= 2:
        base_c = comps[0]
        base_def = _varied_center(glyf, base_c.glyphName, {})
        base_var = _varied_center(glyf, base_c.glyphName, width_deltas)
        base_off = getattr(base_c, 'x', 0)
        deltas.append((0, 0))
        if base_def is not None and base_var is not None:
            base_abs_def = base_off + base_def
            base_abs_var = base_off + base_var
            for c in comps[1:]:
                off = getattr(c, 'x', 0)
                c_def = _varied_center(glyf, c.glyphName, {})
                c_var = _varied_center(glyf, c.glyphName, width_deltas)
                if c_def is None or c_var is None:
                    deltas.append((round(off * scale) - off, 0))
                    continue
                relation = (off + c_def) - base_abs_def
                target_abs = base_abs_var + relation
                deltas.append((round(target_abs - off - c_var), 0))
        else:
            for c in comps[1:]:
                off = getattr(c, 'x', 0)
                deltas.append((round(off * scale) - off, 0))
    else:
        deltas = [(round(getattr(c, 'x', 0) * scale) - getattr(c, 'x', 0), 0) for c in comps]

    deltas.append((0, 0))
    deltas.append((aw1 - aw, 0))
    deltas.append((0, 0))
    deltas.append((0, 0))
    return deltas


def _rebuild_stat(f):
    weights = [(100, 'Thin'), (200, 'ExtraLight'), (300, 'Light'), (400, 'Regular'),
               (500, 'Medium'), (600, 'SemiBold'), (700, 'Bold'), (800, 'ExtraBold'),
               (900, 'Black')]
    axes = [
        dict(tag='opsz', name='Optical Size', ordering=0, values=[
            dict(value=14.0, name='Text'), dict(value=32.0, name='Display')]),
        dict(tag='wght', name='Weight', ordering=1, values=[
            dict(value=float(v), name=n, **({'flags': 0x2} if v == 400 else {}))
            for v, n in weights]),
        dict(tag='wdth', name='Width', ordering=2, values=[
            dict(value=WDTH_MIN, name='Condensed'),
            dict(value=WDTH_DEFAULT, name='Normal', flags=0x2, linkedValue=WDTH_MAX),
            dict(value=WDTH_MAX, name='Expanded')]),
    ]
    buildStatTable(f, axes)


def _corner_worker(args):
    chunk, = args
    DP = _W['DP']
    ST = _W['ST']
    MU = _W['MU']
    bglyf = _W['bglyf']
    bhmtx = _W['bhmtx']
    medians = _W['medians']
    extra_cjk = _W['extra_cjk']
    out = {}
    for gn, cp in chunk:
        g = bglyf[gn]
        g.expand(bglyf)
        if not hasattr(g, 'numberOfContours') or g.numberOfContours <= 0:
            continue
        cjk = is_cjk(cp)
        wg, reliable = ST.get_stem_width(bglyf, gn, cjk, medians)
        if cjk and reliable:
            mult = MU.cjk_stem_multiplier(S_CONDENSE, wg) * extra_cjk
            res = DP.displace_v2(bglyf, gn, S_CONDENSE, wg, mult, allow_diag=True)
        else:
            opening = MU.latin_stem_multiplier(S_ROUND_CONDENSE)
            if cp is not None and chr(cp) in _MIXED_GLYPHS:
                opening *= S_MIXED_OPENING
            res = DP.displace_v2(bglyf, gn, S_ROUND_CONDENSE, wg, opening, allow_diag=True)
        if res is None:
            continue
        coords, ends, flags, base, _ = res
        aw, lsb = bhmtx[gn]
        bxs = [x for x, y in base]
        rsb = aw - lsb - (max(bxs) - min(bxs))
        dl, _ = DP.finalize_metrics(coords, base, lsb, rsb, aw, S_CONDENSE)
        out[gn] = [(base[i][0] + dl[i][0], base[i][1] + dl[i][1]) for i in range(len(base))]
    return out


def _corner_init(blackpath, medians, extra_latin, extra_cjk):
    _W['DP'] = _load('wdth_displace', 'wdth_displace.py')
    _W['ST'] = _load('wdth_stems', 'wdth_stems.py')
    _W['MU'] = _load('wdth_multipliers', 'wdth_multipliers.py')
    _W['ST'].set_fallback_stem(medians.get('fallback'))
    bf = TTFont(blackpath)
    _W['bglyf'] = bf['glyf']
    _W['bhmtx'] = bf['hmtx']
    _W['medians'] = medians
    _W['extra_latin'] = extra_latin
    _W['extra_cjk'] = extra_cjk


def _add_corner_corrections(f, src):
    from fontTools.varLib.instancer import instantiateVariableFont

    extra_latin = 0.82
    extra_cjk = 0.80
    min_corr = 3

    # Round latin glyphs use S_ROUND_CONDENSE (less-condensed bowl body) for full wall
    # restoration with an open counter; round CJK glyphs keep the mult*extra_cjk
    # counter-opening path. Straight-stem glyphs (I l H E T F M N h k ...) are excluded:
    # the correction only over-thins their stems (Bold I 82% vs 98%) without needing help.
    latin_set = set(
        'BCDGOPQRSU'
        'abcdegopqs'
        '0689'
        '&$@'
    ) | set('\u00e6\u0153\u00df')

    black = TTFont(src)
    instantiateVariableFont(black, {'opsz': 14, 'wght': 900}, inplace=True)
    bcmap = black.getBestCmap()
    brev = {}
    for cp, gn in bcmap.items():
        brev.setdefault(gn, cp)
    ST = _load('wdth_stems', 'wdth_stems.py')
    bglyf = black['glyf']
    fallback = ST.compute_fallback_stem(bglyf, bcmap)
    medians = _compute_medians(src)
    medians['fallback'] = fallback
    blackpath = '/tmp/_wdth_black.ttf'
    black.save(blackpath)

    jobs = []
    for gn in black.getGlyphOrder():
        cp = brev.get(gn)
        if cp is None:
            continue
        if not (is_cjk(cp) or (chr(cp) in latin_set if cp < 0x250 else False)):
            continue
        jobs.append((gn, cp))

    nproc = min(cpu_count(), 14)
    size = 64
    chunks = [(jobs[i:i + size],) for i in range(0, len(jobs), size)]
    desired = {}
    with Pool(nproc, initializer=_corner_init, initargs=(blackpath, medians, extra_latin, extra_cjk)) as pool:
        for r in pool.imap_unordered(_corner_worker, chunks):
            desired.update(r)

    corner_path = '/tmp/_wdth_inprogress.ttf'
    f.save(corner_path)
    cur = TTFont(corner_path)
    instantiateVariableFont(cur, {'opsz': 14, 'wght': 900, 'wdth': WDTH_MIN}, inplace=True)
    cglyf = cur['glyf']
    gvar = f['gvar']
    added = 0
    for gn, des in desired.items():
        cg = cglyf[gn]
        cg.expand(cglyf)
        cur_pts = [(x, y) for x, y in cg.coordinates]
        n = min(len(des), len(cur_pts))
        corr = [(round(des[i][0] - cur_pts[i][0]), round(des[i][1] - cur_pts[i][1])) for i in range(n)]
        if not corr or max(abs(d[0]) + abs(d[1]) for d in corr) < min_corr:
            continue
        while len(corr) < len(cur_pts) + 4:
            corr.append((0, 0))
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wght': (0.0, 1.0, 1.0), 'wdth': (-1.0, -1.0, 0.0)}, corr))
        added += 1
    return added


def _apply_wght_evenness_avar(f):
    if 'avar' not in f:
        return
    # Remap the wght axis to SF Pro's stem-progression curve. Interlude's stems are
    # near-linear in wght (n stem 22->190 per 1000UPM), while SF Pro's Thin end is
    # heavier with a flatter low curve (SF Thin n=36 vs Interlude 22). Without this,
    # Thin reads ~40% lighter than SF Pro and looks invisible. The map pulls light
    # weights toward heavier interpolation positions (wght=100 -> ~167 internally,
    # matching SF stem 36). The heavier Thin also masks the small curve-vs-stem
    # thickness gap (o side vs l stem ~6u) that is visually distracting at hairline
    # weight. wght=400 stays fixed and the wght=900 endpoint keeps full reach.
    seg = f['avar'].segments
    wght = dict(seg.get('wght', {}))
    wght.update({
        -1.0: -0.77778,
        -0.66667: -0.52381,
        -0.33333: -0.25397,
        0.0: 0.0,
        0.2: 0.18095,
        0.4: 0.36190,
        0.6: 0.55238,
        0.8: 0.73333,
        1.0: 1.0,
    })
    seg['wght'] = dict(sorted(wght.items()))


# Latin wght=900 stem을 얇게 잘라 CJK 줄기 굵기와 맞춘다 (400 고정, 900으로 점진).
# wght peak 튜플 (0,1,1)만 스케일 → wght=400(norm0)에서 scalar 0이라 불변,
# wght=900(norm1.0)에서 델타가 LATIN_WGHT_THIN_SCALE배. CJK 델타는 별도라 무영향.
LATIN_WGHT_THIN_SCALE = 0.82  # I stem 404->331 at Black (-8%); tapers to 0 at Regular.


THIN_CORR_SCALE = 0.30
THIN_CORR_BOOST = 1.06


def _thin_corr_worker(args):
    chunk, = args
    DP = _W['DP']
    ST = _W['ST']
    MU = _W['MU']
    glyf = _W['glyf']
    medians = _W['medians']
    out = {}
    for gn, cp in chunk:
        g = glyf[gn]
        g.expand(glyf)
        if not hasattr(g, 'numberOfContours') or g.numberOfContours <= 0:
            continue
        cjk = is_cjk(cp)
        wg, reliable = ST.get_stem_width(glyf, gn, cjk, medians)
        if cjk and reliable:
            mult = MU.cjk_stem_multiplier(S_CONDENSE, wg)
        else:
            mult = MU.latin_stem_multiplier(S_CONDENSE)
        rb = DP.displace_v2(glyf, gn, S_CONDENSE, wg, mult, allow_anchor=False, allow_diag=True)
        rh = DP.displace_v2(glyf, gn, S_CONDENSE, wg, mult * THIN_CORR_BOOST, allow_anchor=False, allow_diag=True)
        if rb is None or rh is None:
            continue
        cb = rb[0]
        chh = rh[0]
        n = min(len(cb), len(chh))
        corr = [(round(THIN_CORR_SCALE * (chh[i][0] - cb[i][0])),
                 round(THIN_CORR_SCALE * (chh[i][1] - cb[i][1]))) for i in range(n)]
        if not corr or max(abs(d[0]) + abs(d[1]) for d in corr) < 1:
            continue
        out[gn] = corr
    return out


def _thin_corr_init(src, medians):
    _W['DP'] = _load('wdth_displace', 'wdth_displace.py')
    _W['ST'] = _load('wdth_stems', 'wdth_stems.py')
    _W['MU'] = _load('wdth_multipliers', 'wdth_multipliers.py')
    _W['ST'].set_fallback_stem(medians.get('fallback'))
    f = TTFont(src)
    _W['glyf'] = f['glyf']
    _W['medians'] = medians


def _add_thin_correction(f, src):
    # The condense tuple's stem-restoration is an absolute amount fixed at the
    # wght=400 master, so light weights over-thin (Thin I stem ~89% vs Regular 97%).
    # Inject a thin-side wght x wdth correction = 0.30 * (displace(mult*1.06) -
    # displace(mult)), zero at Regular and full at Thin, lifting Thin stems to ~96%
    # without touching Regular/Bold. Scale 0.30 found empirically against the target.
    medians = _compute_medians(src)
    rev = {}
    for cp, gn in TTFont(src).getBestCmap().items():
        rev.setdefault(gn, cp)
    jobs = []
    for gn in f.getGlyphOrder():
        cp = rev.get(gn)
        if cp is None or not (is_cjk(cp) or is_latin_base(cp)):
            continue
        jobs.append((gn, cp))
    nproc = min(cpu_count(), 14)
    size = 64
    chunks = [(jobs[i:i + size],) for i in range(0, len(jobs), size)]
    corrs = {}
    with Pool(nproc, initializer=_thin_corr_init, initargs=(src, medians)) as pool:
        for r in pool.imap_unordered(_thin_corr_worker, chunks):
            corrs.update(r)
    gvar = f['gvar']
    glyf = f['glyf']
    added = 0
    for gn, corr in corrs.items():
        g = glyf[gn]
        g.expand(glyf)
        npts = len(g.coordinates)
        c = list(corr[:npts])
        while len(c) < npts + 4:
            c.append((0, 0))
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wght': (-1.0, -1.0, 0.0), 'wdth': (-1.0, -1.0, 0.0)}, c))
        added += 1
    return added


def _add_e_overlap_correction(f, src):
    DG = _load('wdth_diagonal', 'wdth_diagonal.py')
    cmap = f.getBestCmap()
    glyf = f['glyf']
    gvar = f['gvar']
    gn = cmap.get(ord('e'))
    if gn is None:
        return 0
    g = glyf[gn]
    g.expand(glyf)
    if not hasattr(g, 'numberOfContours') or g.numberOfContours <= 0:
        return 0
    coords = [(x, y) for x, y in g.coordinates]
    ends = list(g.endPtsOfContours)
    flags = list(g.flags)
    corr = DG.e_overlap_wall_pull(coords, ends, flags)
    if not corr:
        return 0
    npts = len(coords)

    def _tuple_for(scale, axes):
        c = [corr.get(i, (0, 0)) for i in range(npts)]
        c = [(round(dx * scale), round(dy * scale)) for dx, dy in c]
        if max(abs(d[0]) + abs(d[1]) for d in c) < 1:
            return None
        while len(c) < npts + 4:
            c.append((0, 0))
        return TupleVariation(axes, c)

    added = 0
    specs = [
        (9.0 / 13.0, {'wdth': (0.0, 1.0, 1.0)}),
        (4.0 / 13.0, {'wght': (-1.0, -1.0, 0.0), 'wdth': (0.0, 1.0, 1.0)}),
        (-4.0 / 13.0, {'wght': (0.0, 1.0, 1.0), 'wdth': (0.0, 1.0, 1.0)}),
    ]
    for scale, axes in specs:
        tv = _tuple_for(scale, axes)
        if tv is not None:
            gvar.variations.setdefault(gn, []).append(tv)
            added += 1
    return added


def _apply_latin_wght_thinning(f):
    cmap = f.getBestCmap()
    g2cp = {}
    for cp, gn in cmap.items():
        g2cp.setdefault(gn, cp)
    s = LATIN_WGHT_THIN_SCALE
    gv = f['gvar']
    touched = 0
    for gn, tvs in gv.variations.items():
        if not is_latin_base(g2cp.get(gn)):
            continue
        for tv in tvs:
            ax = tv.axes
            if ax.get('wght') == (0.0, 1.0, 1.0) and 'wdth' not in ax and 'opsz' not in ax:
                tv.coordinates = [
                    ((round(p[0] * s), round(p[1] * s)) if p else p)
                    for p in tv.coordinates
                ]
                touched += 1
    return touched


def add_wdth(src, out):
    t0 = time.time()
    print('  Measuring class stem medians...', flush=True)
    medians = _compute_medians(src)
    print(f'    medians cjk={medians["cjk"]:.0f} latin={medians["latin"]:.0f} ({time.time() - t0:.0f}s)', flush=True)
    print('  Computing condensation (wdth=75) deltas...', flush=True)
    cond = _compute(src, S_CONDENSE, medians)
    print(f'    {len(cond)} glyphs ({time.time() - t0:.0f}s)', flush=True)
    print('  Computing expansion (wdth=125) deltas...', flush=True)
    expand = _compute(src, S_EXPAND, medians)
    print(f'    {len(expand)} glyphs ({time.time() - t0:.0f}s)', flush=True)

    f = TTFont(src)
    glyf = f['glyf']
    gvar = f['gvar']
    hmtx = f['hmtx']
    _add_axis_and_instances(f)

    relaxed = 0
    for gn, (deltas, seff) in cond.items():
        if seff > S_CONDENSE:
            relaxed += 1
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (-1.0, -1.0, 0.0)}, deltas))
    for gn, (deltas, seff) in expand.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (0.0, 1.0, 1.0)}, deltas))

    comp = 0
    for gn in f.getGlyphOrder():
        g = glyf[gn]
        g.expand(glyf)
        if not hasattr(g, 'numberOfContours') or g.numberOfContours >= 0:
            continue
        aw, lsb = hmtx[gn]
        g.recalcBounds(glyf)
        rsb = aw - lsb - (g.xMax - g.xMin)
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (-1.0, -1.0, 0.0)}, _composite_deltas(g.components, aw, lsb, rsb, S_CONDENSE, glyf, cond)))
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (0.0, 1.0, 1.0)}, _composite_deltas(g.components, aw, lsb, rsb, S_EXPAND, glyf, expand)))
        comp += 1

    ncorner = _add_corner_corrections(f, src)
    print(f'  corner corrections (Condensed-Black counter opening): {ncorner} glyphs', flush=True)
    nthincorr = _add_thin_correction(f, src)
    print(f'  thin condense correction (light-weight stem lift): {nthincorr} glyphs', flush=True)
    necorr = _add_e_overlap_correction(f, src)
    print(f'  e overlap correction (thin-expand eye gap): {necorr} glyphs', flush=True)
    _rebuild_stat(f)
    _sync_variation_tables(f)
    _apply_wght_evenness_avar(f)
    nthin = _apply_latin_wght_thinning(f)
    print(f'  latin wght thinning (heavy -3%): {nthin} glyphs', flush=True)
    _strip_mac_names(f)
    f.save(out)
    print(f'  wdth axis added: simple={len(cond)} ({relaxed} relaxed) composite={comp} '
          f'({time.time() - t0:.0f}s total)', flush=True)


if __name__ == '__main__':
    add_wdth(sys.argv[1], sys.argv[2])
