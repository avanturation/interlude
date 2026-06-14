"""Add wdth (Width) variable axis to Interlude VF — v2 clean rewrite.

Methodology:
  - Latin/Greek/Cyrillic: Monotone protected-zone x-warp.
    Detects vertical stem x-intervals via scanline analysis, preserves their
    width (slope ~1.0 in the warp map), compresses counters/sidebearings to
    hit the target advance width. Falls back to pure affine if infeasible.
  - CJK (Hangul, Kanji, Kana): Centered affine x-scaling.
    Consistent global behavior; no per-glyph heuristics.
  - Composites: Scale component x-offsets and advance widths.

The result is injected as gvar TupleVariations on the wdth axis.
No per-point normals, no lambda solving, no self-intersection guards.
"""
import sys
import os
import time
import math
import unicodedata as _ud
import importlib.util
from multiprocessing import Pool, cpu_count

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables._f_v_a_r import Axis, NamedInstance
from fontTools.ttLib.tables import otTables
from fontTools.otlLib.builder import buildStatTable

WDTH_MIN = 75.0
WDTH_DEFAULT = 100.0
WDTH_MAX = 125.0

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SFPRO_WDTH_CPS = _load_module('wdth_sfpro_cps', 'wdth_sfpro_cps.py').SFPRO_WDTH_CPS


def is_wdth_excluded(cp):
    """Whitelist model (follows SF Pro): vary real letters/digits and CJK; leave
    arrows, pictographs, box drawing and other non-letter symbols fixed."""
    if cp is None:
        return True
    if is_cjk(cp):
        return False
    try:
        cat = _ud.category(chr(cp))
    except (ValueError, TypeError):
        return True
    if cat[0] in ('L', 'N', 'M'):
        return False
    return cp not in _SFPRO_WDTH_CPS

STEM_PRESERVE = 0.85
DIAG_PRESERVE = 0.93
MIN_COUNTER = 40.0
N_SCAN = 16
SCAN_LO = 0.15
SCAN_HI = 0.85
MIN_STEM_WIDTH = 40.0
MAX_STEM_WIDTH = 280.0
MIN_DIAG_ANGLE = 15.0   # degrees from vertical
MAX_DIAG_ANGLE = 60.0   # degrees from vertical
MIN_DIAG_LENGTH = 150.0 # minimum segment length to qualify


def is_cjk(cp):
    """CJK codepoint ranges (Hangul, Kanji, Kana, symbols)."""
    return cp is not None and (
        0xAC00 <= cp <= 0xD7A3 or
        0x3400 <= cp <= 0x9FFF or
        0xF900 <= cp <= 0xFAFF or
        0x3040 <= cp <= 0x30FF or
        0x3000 <= cp <= 0x303F or
        0xFF00 <= cp <= 0xFFEF or
        0x1100 <= cp <= 0x11FF or
        0x3130 <= cp <= 0x318F
    )



def _flatten_contours_simple(coords, ends, flags):
    """Flatten TrueType quadratic contours to polygons for scanline stem detection."""
    out = []
    start = 0
    for e in ends:
        m = e - start + 1
        raw = [(coords[start + i][0], coords[start + i][1],
                bool(flags[start + i] & 1)) for i in range(m)]
        start = e + 1
        pts = []
        n = len(raw)
        for i in range(n):
            pts.append(raw[i])
            cur = raw[i]
            nxt = raw[(i + 1) % n]
            if not cur[2] and not nxt[2]:
                pts.append(((cur[0] + nxt[0]) / 2, (cur[1] + nxt[1]) / 2, True))
        nn = len(pts)
        first_on = next((k for k in range(nn) if pts[k][2]), None)
        if first_on is None:
            continue
        seq = pts[first_on:] + pts[:first_on]
        nn = len(seq)
        poly = []
        k = 0
        while k < nn:
            x, y, on = seq[k]
            poly.append((x, y))
            nk = (k + 1) % nn
            nx, ny, non = seq[nk]
            if not non:
                ex, ey, _ = seq[(k + 2) % nn]
                for t in (0.25, 0.5, 0.75):
                    mt = 1 - t
                    bx = mt * mt * x + 2 * mt * t * nx + t * t * ex
                    by = mt * mt * y + 2 * mt * t * ny + t * t * ey
                    poly.append((bx, by))
                k += 2
            else:
                k += 1
        if len(poly) >= 3:
            out.append(poly)
    return out


def _scan_at_y(polys, y):
    crossings = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1)
                crossings.append(x1 + t * (x2 - x1))
    crossings.sort()
    return crossings


def _detect_stems(polys, ymin, ymax, body_width=0):
    """Detect vertical stem x-intervals via multi-scanline voting.

    Returns list of (x_left, x_right) tuples representing stem zones.
    A stem is a consistent-width dark run that persists across multiple scanlines.
    """
    yspan = ymax - ymin
    if yspan < 10:
        return []

    max_stem = body_width * 0.5 if body_width > 0 else MAX_STEM_WIDTH

    runs_by_scan = []
    for i in range(N_SCAN):
        frac = SCAN_LO + (SCAN_HI - SCAN_LO) * i / (N_SCAN - 1)
        y = ymin + yspan * frac
        xs = _scan_at_y(polys, y)
        runs = []
        for j in range(0, len(xs) - 1, 2):
            w = xs[j + 1] - xs[j]
            if MIN_STEM_WIDTH <= w <= max_stem:
                runs.append((xs[j], xs[j + 1], w))
        runs_by_scan.append(runs)

    stems = []
    if not runs_by_scan:
        return stems

    candidates = {}
    for runs in runs_by_scan:
        for xl, xr, w in runs:
            xc = (xl + xr) / 2
            placed = False
            for key in list(candidates.keys()):
                if abs(xc - key) < max(60.0, w * 0.5):
                    candidates[key]['count'] += 1
                    candidates[key]['xls'].append(xl)
                    candidates[key]['xrs'].append(xr)
                    placed = True
                    break
            if not placed:
                candidates[xc] = {'count': 1, 'xls': [xl], 'xrs': [xr]}

    min_support = max(3, N_SCAN // 3)
    for key, data in candidates.items():
        if data['count'] >= min_support:
            xls = sorted(data['xls'])
            xrs = sorted(data['xrs'])
            xl = xls[len(xls) // 2]
            xr = xrs[len(xrs) // 2]
            if xr - xl > max_stem:
                continue
            w = xr - xl
            max_spread = max(xls[-1] - xls[0], xrs[-1] - xrs[0])
            if data['count'] < 12 and max_spread > w * 0.6:
                continue
            stems.append((xl, xr))

    stems.sort()
    merged = []
    for s in stems:
        if merged and s[0] < merged[-1][1] + 20:
            new_w = max(merged[-1][1], s[1]) - merged[-1][0]
            if new_w <= max_stem:
                merged[-1] = (merged[-1][0], max(merged[-1][1], s[1]))
            else:
                merged.append(s)
        else:
            merged.append(s)
    return merged


def _build_monotone_warp(x_min, x_max, stems, target_width, original_width):
    """Build smooth monotone x-mapping with stem preservation.

    Instead of hard piecewise-linear slope changes at stem boundaries, this
    builds a dense warp table with cosine-eased transitions over a shoulder
    band around each stem edge.  The result is C1-continuous, preventing
    tangent kinks at zone boundaries.
    """
    if not stems or abs(target_width - original_width) < 1:
        s = target_width / original_width if original_width > 0 else 1.0
        center = (x_min + x_max) / 2
        return [(x_min, center + (x_min - center) * s),
                (x_max, center + (x_max - center) * s)]

    s = target_width / original_width
    condensing = (s < 1.0)

    total_stem_width = sum(xr - xl for xl, xr in stems)
    total_flex_width = original_width - total_stem_width

    if total_flex_width < 1:
        center = (x_min + x_max) / 2
        return [(x_min, center + (x_min - center) * s),
                (x_max, center + (x_max - center) * s)]

    if condensing:
        stem_slope = STEM_PRESERVE
        needed_flex = target_width - total_stem_width * stem_slope
        if total_flex_width < 1 or needed_flex < MIN_COUNTER * len(stems):
            center = (x_min + x_max) / 2
            return [(x_min, center + (x_min - center) * s),
                    (x_max, center + (x_max - center) * s)]
        flex_scale = needed_flex / total_flex_width
        if flex_scale < 0.55:
            flex_scale = 0.55
            stem_slope = (target_width - flex_scale * total_flex_width) / total_stem_width
    else:
        stem_slope = 1.0 + (s - 1.0) * 0.46
        needed_flex = target_width - total_stem_width * stem_slope
        if total_flex_width < 1:
            center = (x_min + x_max) / 2
            return [(x_min, center + (x_min - center) * s),
                    (x_max, center + (x_max - center) * s)]
        flex_scale = needed_flex / total_flex_width
        if flex_scale > 1.8:
            flex_scale = 1.8
            stem_slope = (target_width - flex_scale * total_flex_width) / total_stem_width

    # Cosine-eased slope transition: shoulder band = 25% of narrower neighbor
    SHOULDER_FRAC = 0.25
    breakpoints_in = [x_min]
    for xl, xr in stems:
        breakpoints_in.append(xl)
        breakpoints_in.append(xr)
    breakpoints_in.append(x_max)

    segments = []
    for i in range(len(breakpoints_in) - 1):
        seg_start = breakpoints_in[i]
        seg_end = breakpoints_in[i + 1]
        is_stem = False
        for xl, xr in stems:
            if abs(seg_start - xl) < 1 and abs(seg_end - xr) < 1:
                is_stem = True
                break
        segments.append((seg_start, seg_end, is_stem))

    N_SAMPLES = 128
    step = (x_max - x_min) / N_SAMPLES
    if step < 0.5:
        step = 0.5
        N_SAMPLES = int((x_max - x_min) / step)

    def _get_base_slope(x):
        for seg_start, seg_end, is_stem in segments:
            if seg_start - 0.01 <= x <= seg_end + 0.01:
                return stem_slope if is_stem else flex_scale
        return flex_scale

    def _smooth_slope(x):
        inner_boundaries = []
        for xl, xr in stems:
            inner_boundaries.append(xl)
            inner_boundaries.append(xr)

        if not inner_boundaries:
            return _get_base_slope(x)

        base_slope = _get_base_slope(x)

        for bx in inner_boundaries:
            left_seg_w = None
            right_seg_w = None
            for seg_start, seg_end, _ in segments:
                if abs(seg_end - bx) < 1:
                    left_seg_w = seg_end - seg_start
                if abs(seg_start - bx) < 1:
                    right_seg_w = seg_end - seg_start

            min_neighbor = min(
                left_seg_w if left_seg_w else 1e9,
                right_seg_w if right_seg_w else 1e9
            )
            shoulder = min_neighbor * SHOULDER_FRAC
            shoulder = max(shoulder, 8.0)
            shoulder = min(shoulder, 60.0)

            dist = x - bx
            if abs(dist) < shoulder:
                slope_left = _get_base_slope(bx - 1)
                slope_right = _get_base_slope(bx + 1)
                # Cosine ease: t ∈ [0,1] blends slope_left → slope_right
                t = (dist + shoulder) / (2.0 * shoulder)
                t = max(0.0, min(1.0, t))
                t = 0.5 - 0.5 * math.cos(t * math.pi)
                blended = slope_left + (slope_right - slope_left) * t
                return blended

        return base_slope

    # Integrate smooth slope → output positions
    offset = (original_width - target_width) / 2
    warp_points = [(x_min, x_min + offset)]
    cursor = x_min + offset

    for i in range(1, N_SAMPLES + 1):
        x_prev = x_min + (i - 1) * step
        x_cur = x_min + i * step
        if x_cur > x_max:
            x_cur = x_max
        dx = x_cur - x_prev
        mid_x = (x_prev + x_cur) / 2.0
        slope_at_mid = _smooth_slope(mid_x)
        cursor += dx * slope_at_mid
        warp_points.append((x_cur, cursor))

    actual_out_width = warp_points[-1][1] - warp_points[0][1]
    if abs(actual_out_width) > 0.01 and abs(actual_out_width - target_width) > 0.5:
        correction = target_width / actual_out_width
        base_out = warp_points[0][1]
        warp_points = [(xi, base_out + (yo - base_out) * correction)
                       for xi, yo in warp_points]

    return warp_points


def _apply_warp(x, warp_map):
    if not warp_map:
        return x
    if x <= warp_map[0][0]:
        return warp_map[0][1]
    if x >= warp_map[-1][0]:
        return warp_map[-1][1]
    lo, hi = 0, len(warp_map) - 1
    while lo < hi - 1:
        mid = (lo + hi) >> 1
        if warp_map[mid][0] <= x:
            lo = mid
        else:
            hi = mid
    x0, y0 = warp_map[lo]
    x1, y1 = warp_map[hi]
    if abs(x1 - x0) < 1e-6:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


_W = {}


def _init_worker(src):
    f = TTFont(src)
    _W['glyf'] = f['glyf']
    _W['hmtx'] = f['hmtx']
    cmap = f.getBestCmap()
    rev = {}
    for cp, gn in cmap.items():
        rev.setdefault(gn, cp)
    _W['rev'] = rev


def _process_glyph(args):
    gn, scale = args
    glyf = _W['glyf']
    hmtx = _W['hmtx']
    rev = _W['rev']

    g = glyf[gn]
    g.expand(glyf)
    if not hasattr(g, 'numberOfContours') or g.numberOfContours <= 0:
        return None

    cp = rev.get(gn)
    if is_wdth_excluded(cp):
        return None
    coords = [(x, y) for x, y in g.coordinates]
    ends = list(g.endPtsOfContours)
    flags = list(g.flags)
    n_pts = len(coords)

    if n_pts == 0:
        return None

    aw, lsb = hmtx[gn]
    xs = [x for x, y in coords]
    ys = [y for x, y in coords]
    x_min_g, x_max_g = min(xs), max(xs)
    y_min_g, y_max_g = min(ys), max(ys)
    body_width = x_max_g - x_min_g
    rsb = aw - lsb - body_width

    target_aw = round(aw * scale)

    if is_cjk(cp):
        new_coords = _process_cjk(coords, aw, scale)
    else:
        new_coords = _process_latin(
            coords, ends, flags, aw, lsb, rsb,
            x_min_g, x_max_g, y_min_g, y_max_g, scale)

    new_xs = [nc[0] for nc in new_coords]
    new_x_min = min(new_xs)

    # SF Pro sidebearing pattern: SB barely grows when expanding,
    # and shrinks less than body when condensing.
    # Measured: expanded SB_scale≈0.985 when body_scale=1.293
    #           condensed SB_scale≈0.905 when body_scale=0.829
    # Model: sb_scale = 1.0 + (scale - 1.0) * SB_DAMP
    SB_DAMP = 0.10
    sb_scale = 1.0 + (scale - 1.0) * SB_DAMP
    target_lsb = round(lsb * sb_scale) if lsb >= 0 else lsb
    shift = target_lsb - new_x_min
    new_coords = [(x + shift, y) for x, y in new_coords]

    deltas = [(round(new_coords[i][0]) - coords[i][0],
               round(new_coords[i][1]) - coords[i][1]) for i in range(n_pts)]

    new_body = max(new_xs) - new_x_min
    target_rsb = round(rsb * sb_scale) if rsb >= 0 else rsb
    target_aw = round(target_lsb + new_body + target_rsb) if not is_cjk(cp) else round(aw * scale)
    phantoms = [(0, 0), (target_aw - aw, 0), (0, 0), (0, 0)]
    return gn, deltas + phantoms


def _process_cjk(coords, aw, scale):
    """CJK: centered affine x-scaling. Simple, globally consistent."""
    center = aw / 2.0
    return [(center + (x - center) * scale, y) for x, y in coords]


def _repair_diagonal_tangents(orig_coords, new_coords, ends, flags):
    """Fix tangent breaks at line→curve junctions caused by non-uniform x-warp.

    When a straight diagonal (ON→ON) meets a curve (ON→off), the warp changes
    the diagonal's angle but not the curve handle's direction. This rotates the
    first off-curve point to restore the original tangent continuity.
    """
    result = list(new_coords)
    n = len(orig_coords)
    start = 0
    for end in ends:
        cnt = end - start + 1
        for i in range(cnt):
            idx = start + i
            if not (flags[idx] & 1):
                continue
            prev_idx = start + ((i - 1) % cnt)
            next_idx = start + ((i + 1) % cnt)

            prev_on = bool(flags[prev_idx] & 1)
            next_off = not bool(flags[next_idx] & 1)
            if not (prev_on and next_off):
                continue

            # line→curve junction at idx
            # Original tangent angle at junction
            opx, opy = orig_coords[prev_idx]
            ocx, ocy = orig_coords[idx]
            onx, ony = orig_coords[next_idx]

            oin_dx, oin_dy = ocx - opx, ocy - opy
            oout_dx, oout_dy = onx - ocx, ony - ocy
            if (oin_dx**2 + oin_dy**2) < 4 or (oout_dx**2 + oout_dy**2) < 4:
                continue

            orig_kink = math.atan2(oout_dy, oout_dx) - math.atan2(oin_dy, oin_dx)
            if orig_kink > math.pi: orig_kink -= 2*math.pi
            if orig_kink < -math.pi: orig_kink += 2*math.pi

            # Skip intentional design corners (>15° = serif curls, etc.)
            if abs(orig_kink) > 0.26:
                continue

            # Warped tangent angle
            npx, npy = result[prev_idx]
            ncx, ncy = result[idx]
            nnx, nny = result[next_idx]

            nin_dx, nin_dy = ncx - npx, ncy - npy
            nout_dx, nout_dy = nnx - ncx, nny - ncy
            if (nin_dx**2 + nin_dy**2) < 4 or (nout_dx**2 + nout_dy**2) < 4:
                continue

            new_kink = math.atan2(nout_dy, nout_dx) - math.atan2(nin_dy, nin_dx)
            if new_kink > math.pi: new_kink -= 2*math.pi
            if new_kink < -math.pi: new_kink += 2*math.pi

            # Only fix diagonal lines (20-70° from horizontal)
            in_angle = abs(math.degrees(math.atan2(abs(nin_dy), abs(nin_dx))))
            if not (15 < in_angle < 75):
                continue

            # Rotation needed to restore original kink
            rot = orig_kink - new_kink
            if abs(rot) < 0.002:
                continue

            # Rotate the off-curve point around the junction
            dist = (nout_dx**2 + nout_dy**2)**0.5
            target_angle = math.atan2(nin_dy, nin_dx) + orig_kink
            result[next_idx] = (
                ncx + dist * math.cos(target_angle),
                ncy + dist * math.sin(target_angle)
            )
        start = end + 1
    return result


def _preserve_diagonal_strokes(orig_coords, new_coords, ends, flags, scale):
    """Preserve diagonal stroke perpendicular width after x-warp.

    Detects paired diagonal edges (inner/outer of same stroke), measures
    the original perpendicular width, then adjusts warped points so the
    perpendicular width is maintained at the SF Pro-calibrated ratio:
      stroke_scale = 1.0 + (scale - 1.0) * DIAG_FACTOR
    where DIAG_FACTOR ≈ 0.58 (from SF Pro measurement).

    Corrections are applied symmetrically around the warped centerline
    with smooth falloff near endpoints/apices.
    """
    DIAG_FACTOR = 0.40
    result = list(new_coords)

    # Step 1: Find all diagonal segments (ON→ON, steep angle)
    segments = []
    start = 0
    for end in ends:
        cnt = end - start + 1
        for i in range(cnt):
            idx = start + i
            if not (flags[idx] & 1):
                continue
            ni = (i + 1) % cnt
            nidx = start + ni
            if not (flags[nidx] & 1):
                continue
            ox1, oy1 = orig_coords[idx]
            ox2, oy2 = orig_coords[nidx]
            dx = abs(ox2 - ox1)
            dy = abs(oy2 - oy1)
            if dy < MIN_DIAG_LENGTH or dx < 50:
                continue
            angle_from_horiz = math.degrees(math.atan2(dy, dx))
            if not (25 < angle_from_horiz < 80):
                continue
            if oy1 > oy2:
                segments.append((idx, nidx, ox1, oy1, ox2, oy2))
            else:
                segments.append((nidx, idx, ox2, oy2, ox1, oy1))
        start = end + 1

    if not segments:
        return result

    segments.sort(key=lambda s: abs(s[3]-s[5]), reverse=True)

    # Step 2: Pair segments that form opposite edges of the same stroke.
    # Two segments are paired if they have similar angle, overlapping y-range,
    # and consistent x-separation (inner is always closer to glyph center).
    paired = []
    used = set()
    for i, (idx_a, nidx_a, ax1, ay1, ax2, ay2) in enumerate(segments):
        if i in used:
            continue
        dir_a = (ax2 - ax1, ay2 - ay1)
        angle_a = math.atan2(dir_a[1], dir_a[0])

        best_j = -1
        best_overlap = 0
        for j, (idx_b, nidx_b, bx1, by1, bx2, by2) in enumerate(segments):
            if j <= i or j in used:
                continue
            dir_b = (bx2 - bx1, by2 - by1)
            angle_b = math.atan2(dir_b[1], dir_b[0])

            da = abs(angle_a - angle_b)
            if da > math.pi:
                da = 2 * math.pi - da
            if da > math.pi / 2:
                da = math.pi - da
            if da > 0.26:
                continue

            ya_lo, ya_hi = min(ay1, ay2), max(ay1, ay2)
            yb_lo, yb_hi = min(by1, by2), max(by1, by2)
            overlap = min(ya_hi, yb_hi) - max(ya_lo, yb_lo)
            if overlap < 100:
                continue

            mid_y = (max(ya_lo, yb_lo) + min(ya_hi, yb_hi)) / 2
            ta = (mid_y - ay1) / (ay2 - ay1) if abs(ay2 - ay1) > 1 else 0.5
            tb = (mid_y - by1) / (by2 - by1) if abs(by2 - by1) > 1 else 0.5
            ta = max(0, min(1, ta))
            tb = max(0, min(1, tb))
            xa_mid = ax1 + ta * (ax2 - ax1)
            xb_mid = bx1 + tb * (bx2 - bx1)
            sep = abs(xa_mid - xb_mid)
            if sep < 10 or sep > 400:
                continue

            if overlap > best_overlap:
                best_overlap = overlap
                best_j = j

        if best_j >= 0:
            paired.append((i, best_j))
            used.add(i)
            used.add(best_j)

    if not paired:
        return result

    # Step 3: Delta dampening for diagonal stroke width preservation.
    # For each paired stroke, reduce the differential x-delta between edges
    # so separation grows by DIAG_FACTOR rate instead of full warp rate.
    for si, sj in paired:
        seg_a = segments[si]
        seg_b = segments[sj]
        idx_a, nidx_a, ax1, ay1, ax2, ay2 = seg_a
        idx_b, nidx_b, bx1, by1, bx2, by2 = seg_b

        ya_lo, ya_hi = min(ay1, ay2), max(ay1, ay2)
        yb_lo, yb_hi = min(by1, by2), max(by1, by2)
        overlap_lo = max(ya_lo, yb_lo)
        overlap_hi = min(ya_hi, yb_hi)
        if overlap_hi - overlap_lo < 50:
            continue

        def delta_at_y(seg, y):
            i0, n0, _, sy1, _, sy2 = seg
            if abs(sy2 - sy1) < 1:
                return ((new_coords[i0][0] - orig_coords[i0][0]) +
                        (new_coords[n0][0] - orig_coords[n0][0])) / 2
            t = (y - sy1) / (sy2 - sy1)
            t = max(0.0, min(1.0, t))
            d0 = new_coords[i0][0] - orig_coords[i0][0]
            d1 = new_coords[n0][0] - orig_coords[n0][0]
            return d0 + t * (d1 - d0)

        dampen = 1.0 - DIAG_FACTOR

        for pt_idx, seg_self, seg_other in [
            (idx_a, seg_a, seg_b), (nidx_a, seg_a, seg_b),
            (idx_b, seg_b, seg_a), (nidx_b, seg_b, seg_a)
        ]:
            py = orig_coords[pt_idx][1]
            py_clamped = max(overlap_lo, min(overlap_hi, py))

            delta_self = new_coords[pt_idx][0] - orig_coords[pt_idx][0]
            delta_other = delta_at_y(seg_other, py_clamped)

            diff = delta_self - delta_other
            correction = -diff * dampen * 0.5

            result[pt_idx] = (new_coords[pt_idx][0] + correction, result[pt_idx][1])

    # Step 4: Propagate corrections to off-curve points via y-interpolation
    for si, sj in paired:
        seg_a = segments[si]
        seg_b = segments[sj]
        idx_a, nidx_a = seg_a[0], seg_a[1]
        idx_b, nidx_b = seg_b[0], seg_b[1]

        corr_a1 = result[idx_a][0] - new_coords[idx_a][0]
        corr_a2 = result[nidx_a][0] - new_coords[nidx_a][0]
        corr_b1 = result[idx_b][0] - new_coords[idx_b][0]
        corr_b2 = result[nidx_b][0] - new_coords[nidx_b][0]

        ya1 = orig_coords[idx_a][1]
        ya2 = orig_coords[nidx_a][1]
        yb1 = orig_coords[idx_b][1]
        yb2 = orig_coords[nidx_b][1]

        for seg_idx, seg_nidx, c1, c2, y1, y2 in [
            (idx_a, nidx_a, corr_a1, corr_a2, ya1, ya2),
            (idx_b, nidx_b, corr_b1, corr_b2, yb1, yb2)
        ]:
            contour_start = 0
            for e in ends:
                if seg_idx <= e:
                    contour_start = 0 if e == ends[0] else ends[ends.index(e)-1] + 1
                    contour_end = e
                    break
            cnt = contour_end - contour_start + 1
            i_local = seg_idx - contour_start
            ni_local = seg_nidx - contour_start
            steps = (ni_local - i_local) % cnt
            if steps <= 1:
                continue
            for s in range(1, steps):
                mid_idx = contour_start + (i_local + s) % cnt
                if mid_idx == seg_idx or mid_idx == seg_nidx:
                    continue
                py = orig_coords[mid_idx][1]
                if abs(y2 - y1) > 1:
                    t = (py - y1) / (y2 - y1)
                    t = max(0, min(1, t))
                else:
                    t = 0.5
                interp_corr = c1 + t * (c2 - c1)
                result[mid_idx] = (
                    new_coords[mid_idx][0] + interp_corr,
                    result[mid_idx][1]
                )

    return result


def _process_latin(coords, ends, flags, aw, lsb, rsb,
                   x_min_g, x_max_g, y_min_g, y_max_g, scale):
    body_width = x_max_g - x_min_g
    if body_width < 10:
        center = aw / 2.0
        return [(center + (x - center) * scale, y) for x, y in coords]

    # Single-stem glyphs (l, I, etc.): body ≈ stem → no warp
    if body_width <= MAX_STEM_WIDTH and len(ends) == 1:
        return list(coords)

    polys = _flatten_contours_simple(coords, ends, flags)
    stems = _detect_stems(polys, y_min_g, y_max_g, body_width) if polys else []

    if stems:
        total_stem = sum(xr - xl for xl, xr in stems)
        stem_body_ratio = total_stem / body_width
        if stem_body_ratio > 0.85 and len(stems) <= 1:
            return list(coords)

    target_body = body_width * scale
    warp_map = _build_monotone_warp(x_min_g, x_max_g, stems, target_body, body_width)

    new_coords = [(_apply_warp(x, warp_map), y) for x, y in coords]
    new_coords = _preserve_diagonal_strokes(coords, new_coords, ends, flags, scale)
    new_coords = _repair_diagonal_tangents(coords, new_coords, ends, flags)
    return new_coords



def _process_composites(f, scale, simple_deltas):
    glyf = f['glyf']
    hmtx = f['hmtx']
    gvar = f['gvar']
    results = {}

    for gn in f.getGlyphOrder():
        g = glyf[gn]
        g.expand(glyf)
        if not hasattr(g, 'numberOfContours') or g.numberOfContours >= 0:
            continue
        if not hasattr(g, 'components') or not g.components:
            continue

        aw, lsb = hmtx[gn]
        if aw < 50:
            continue

        target_aw = round(aw * scale)

        deltas = []
        for ci, comp in enumerate(g.components):
            cx = getattr(comp, 'x', 0)
            comp_gn = comp.glyphName
            comp_aw = hmtx[comp_gn][0] if comp_gn in hmtx.metrics else 0

            if comp_aw >= 50 and ci == 0:
                new_cx = round(cx * scale)
                deltas.append((new_cx - cx, 0))
            elif comp_aw < 50 and ci > 0:
                base_gn = g.components[0].glyphName
                if base_gn in simple_deltas:
                    base_deltas = simple_deltas[base_gn]
                    n_real = len(base_deltas) - 4
                    if n_real > 0:
                        bg = glyf[base_gn]
                        bg.expand(glyf)
                        if bg.numberOfContours > 0 and len(bg.coordinates) == n_real:
                            bg.recalcBounds(glyf)
                            y_mid = (bg.yMin + bg.yMax) / 2
                            top_shifts = [
                                base_deltas[i][0]
                                for i, (x, y) in enumerate(bg.coordinates)
                                if y > y_mid and base_deltas[i] is not None
                            ]
                            if top_shifts:
                                shift = sum(top_shifts) / len(top_shifts)
                            else:
                                shift = sum(
                                    d[0] for d in base_deltas[:n_real] if d
                                ) / n_real
                        else:
                            shift = sum(
                                d[0] for d in base_deltas[:n_real] if d
                            ) / n_real
                        deltas.append((round(shift), 0))
                    else:
                        deltas.append((round(cx * scale) - cx, 0))
                else:
                    deltas.append((round(cx * scale) - cx, 0))
            else:
                new_cx = round(cx * scale)
                deltas.append((new_cx - cx, 0))

        phantoms = [(0, 0), (target_aw - aw, 0), (0, 0), (0, 0)]
        results[gn] = deltas + phantoms

    return results


def _add_axis_and_instances(f):
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
            inst.postscriptNameID = name.addName(
                f'Interlude-{ps_weight}' if ps_weight else 'Interlude-Regular')

    added = []
    for prefix, wd in (('Condensed', WDTH_MIN), ('Expanded', WDTH_MAX)):
        for inst in base:
            weight = name.getDebugName(inst.subfamilyNameID)
            ni = NamedInstance()
            ni.coordinates = dict(inst.coordinates)
            ni.coordinates['wdth'] = wd
            ni.subfamilyNameID = name.addName(f'{prefix} {weight}')
            ps_weight = '' if weight == 'Regular' else weight
            ni.postscriptNameID = name.addName(f'Interlude-{prefix}{ps_weight}')
            added.append(ni)
    fvar.instances.extend(added)


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


def _compute_all(src, scale):
    f = TTFont(src)
    glyf = f['glyf']
    hmtx = f['hmtx']
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
        aw = hmtx[gn][0] if gn in hmtx.metrics else 0
        if aw < 50:
            continue
        jobs.append((gn, scale))

    nproc = min(cpu_count(), 12)
    chunk_size = max(1, len(jobs) // (nproc * 4))
    results = {}

    with Pool(nproc, initializer=_init_worker, initargs=(src,)) as pool:
        for r in pool.imap_unordered(_process_glyph, jobs, chunksize=chunk_size):
            if r is not None:
                gn, deltas = r
                results[gn] = deltas

    return results


def _compute_interaction(src, wght_val, scale):
    """Compute wdth deltas at a specific wght, return delta differences from default."""
    import tempfile, os
    from fontTools.varLib.instancer import instantiateVariableFont

    # Instantiate at the target weight (pins wght, keeps other axes)
    f = TTFont(src)
    instantiateVariableFont(f, {'wght': wght_val, 'opsz': 14}, inplace=True, overlap=0)
    tmp = tempfile.NamedTemporaryFile(suffix='.ttf', delete=False)
    tmp.close()
    f.save(tmp.name)
    try:
        result = _compute_all(tmp.name, scale)
    finally:
        os.unlink(tmp.name)
    return result


def _subtract_deltas(weight_deltas, default_deltas):
    """Compute interaction = weight_specific - default. Only keep non-trivial diffs."""
    interaction = {}
    for gn, w_deltas in weight_deltas.items():
        d_deltas = default_deltas.get(gn)
        if d_deltas is None or len(w_deltas) != len(d_deltas):
            continue
        diff = [(w[0] - d[0], w[1] - d[1]) for w, d in zip(w_deltas, d_deltas)]
        # Skip if interaction is negligible (all diffs < 2 units)
        if any(abs(dx) > 1 or abs(dy) > 1 for dx, dy in diff):
            interaction[gn] = diff
    return interaction


def _process_marks(f, scale_cond, scale_exp, cond_deltas, exp_deltas):
    glyf = f['glyf']
    hmtx = f['hmtx']

    mark_to_bases = {}
    for gn in f.getGlyphOrder():
        g = glyf[gn]
        g.expand(glyf)
        if g.numberOfContours != -1 or not hasattr(g, 'components'):
            continue
        aw = hmtx[gn][0] if gn in hmtx.metrics else 0
        if aw < 50:
            continue
        for ci, comp in enumerate(g.components):
            if ci > 0:
                comp_aw = hmtx[comp.glyphName][0] if comp.glyphName in hmtx.metrics else 0
                if comp_aw < 50:
                    base_gn = g.components[0].glyphName
                    mark_to_bases.setdefault(comp.glyphName, set()).add(base_gn)

    cond_results = {}
    exp_results = {}

    mark_scale_cond = scale_cond * 0.97
    mark_scale_exp = scale_exp * 0.92

    for gn, base_gns in mark_to_bases.items():
        g = glyf[gn]
        g.expand(glyf)
        if g.numberOfContours <= 0:
            continue
        g.recalcBounds(glyf)
        cx = (g.xMin + g.xMax) / 2.0

        cond_d = []
        exp_d = []
        for x, y in g.coordinates:
            dx_c = int(round((x - cx) * mark_scale_cond + cx)) - x
            dx_e = int(round((x - cx) * mark_scale_exp + cx)) - x
            cond_d.append((dx_c, 0))
            exp_d.append((dx_e, 0))

        phantoms = [(0, 0), (0, 0), (0, 0), (0, 0)]
        cond_results[gn] = cond_d + phantoms
        exp_results[gn] = exp_d + phantoms

    return cond_results, exp_results


def _process_marks_interaction(src, mark_gns, wght_val):
    import tempfile, os
    from fontTools.varLib.instancer import instantiateVariableFont

    fi = TTFont(src)
    instantiateVariableFont(fi, {'wght': wght_val, 'opsz': 14}, inplace=True, overlap=0)
    glyf_i = fi['glyf']

    results_cond = {}
    results_exp = {}

    for gn in mark_gns:
        g = glyf_i[gn]
        g.expand(glyf_i)
        if g.numberOfContours <= 0:
            continue
        g.recalcBounds(glyf_i)
        cx = (g.xMin + g.xMax) / 2.0
        w = g.xMax - g.xMin
        if w < 10:
            continue

        cond_d = []
        exp_d = []
        mark_sc = (WDTH_MIN / 100.0) * 0.97
        mark_se = (WDTH_MAX / 100.0) * 0.92
        for x, y in g.coordinates:
            x = float(x)
            dx_c = int(round((x - cx) * mark_sc + cx)) - int(round(x))
            dx_e = int(round((x - cx) * mark_se + cx)) - int(round(x))
            cond_d.append((dx_c, 0))
            exp_d.append((dx_e, 0))

        phantoms = [(0, 0), (0, 0), (0, 0), (0, 0)]
        results_cond[gn] = cond_d + phantoms
        results_exp[gn] = exp_d + phantoms

    return results_cond, results_exp


def add_wdth(src, out):
    t0 = time.time()

    print('  Computing condensed (wdth=75) deltas...', flush=True)
    cond = _compute_all(src, WDTH_MIN / 100.0)
    print(f'    {len(cond)} glyphs ({time.time() - t0:.0f}s)', flush=True)

    print('  Computing expanded (wdth=125) deltas...', flush=True)
    expand = _compute_all(src, WDTH_MAX / 100.0)
    print(f'    {len(expand)} glyphs ({time.time() - t0:.0f}s)', flush=True)

    # Cross-axis interaction: compute wdth deltas at extreme weights
    print('  Computing wght×wdth interaction (Thin)...', flush=True)
    cond_thin = _compute_interaction(src, 100, WDTH_MIN / 100.0)
    exp_thin = _compute_interaction(src, 100, WDTH_MAX / 100.0)
    inter_cond_thin = _subtract_deltas(cond_thin, cond)
    inter_exp_thin = _subtract_deltas(exp_thin, expand)
    print(f'    Thin interaction: {len(inter_cond_thin)}c/{len(inter_exp_thin)}e '
          f'({time.time() - t0:.0f}s)', flush=True)

    print('  Computing wght×wdth interaction (Black)...', flush=True)
    cond_black = _compute_interaction(src, 900, WDTH_MIN / 100.0)
    exp_black = _compute_interaction(src, 900, WDTH_MAX / 100.0)
    inter_cond_black = _subtract_deltas(cond_black, cond)
    inter_exp_black = _subtract_deltas(exp_black, expand)
    print(f'    Black interaction: {len(inter_cond_black)}c/{len(inter_exp_black)}e '
          f'({time.time() - t0:.0f}s)', flush=True)

    f = TTFont(src)
    glyf = f['glyf']
    gvar = f['gvar']
    hmtx = f['hmtx']

    _add_axis_and_instances(f)

    # Base wdth deltas (at default wght)
    for gn, deltas in cond.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (-1.0, -1.0, 0.0)}, deltas))
    for gn, deltas in expand.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (0.0, 1.0, 1.0)}, deltas))

    # Zero-width marks: scale outlines around center to match stem factor
    mark_cond, mark_exp = _process_marks(
        f, WDTH_MIN / 100.0, WDTH_MAX / 100.0, cond, expand)
    mark_gns = set(mark_cond.keys()) | set(mark_exp.keys())
    for gn, deltas in mark_cond.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (-1.0, -1.0, 0.0)}, deltas))
    for gn, deltas in mark_exp.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (0.0, 1.0, 1.0)}, deltas))

    mark_cond_black, mark_exp_black = _process_marks_interaction(src, mark_gns, 900)
    mark_cond_thin, mark_exp_thin = _process_marks_interaction(src, mark_gns, 100)
    for gn in mark_gns:
        if gn in mark_cond_black and gn in mark_cond:
            diff = [(a[0]-b[0], a[1]-b[1]) for a, b in
                    zip(mark_cond_black[gn], mark_cond[gn])]
            if any(abs(d[0]) > 1 for d in diff):
                gvar.variations.setdefault(gn, []).append(
                    TupleVariation({'wght': (0.0, 1.0, 1.0),
                                    'wdth': (-1.0, -1.0, 0.0)}, diff))
        if gn in mark_exp_black and gn in mark_exp:
            diff = [(a[0]-b[0], a[1]-b[1]) for a, b in
                    zip(mark_exp_black[gn], mark_exp[gn])]
            if any(abs(d[0]) > 1 for d in diff):
                gvar.variations.setdefault(gn, []).append(
                    TupleVariation({'wght': (0.0, 1.0, 1.0),
                                    'wdth': (0.0, 1.0, 1.0)}, diff))
        if gn in mark_cond_thin and gn in mark_cond:
            diff = [(a[0]-b[0], a[1]-b[1]) for a, b in
                    zip(mark_cond_thin[gn], mark_cond[gn])]
            if any(abs(d[0]) > 1 for d in diff):
                gvar.variations.setdefault(gn, []).append(
                    TupleVariation({'wght': (-1.0, -1.0, 0.0),
                                    'wdth': (-1.0, -1.0, 0.0)}, diff))
        if gn in mark_exp_thin and gn in mark_exp:
            diff = [(a[0]-b[0], a[1]-b[1]) for a, b in
                    zip(mark_exp_thin[gn], mark_exp[gn])]
            if any(abs(d[0]) > 1 for d in diff):
                gvar.variations.setdefault(gn, []).append(
                    TupleVariation({'wght': (-1.0, -1.0, 0.0),
                                    'wdth': (0.0, 1.0, 1.0)}, diff))

    # Cross-axis interaction tuples (wght×wdth)
    for gn, deltas in inter_cond_thin.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wght': (-1.0, -1.0, 0.0),
                            'wdth': (-1.0, -1.0, 0.0)}, deltas))
    for gn, deltas in inter_exp_thin.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wght': (-1.0, -1.0, 0.0),
                            'wdth': (0.0, 1.0, 1.0)}, deltas))
    for gn, deltas in inter_cond_black.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wght': (0.0, 1.0, 1.0),
                            'wdth': (-1.0, -1.0, 0.0)}, deltas))
    for gn, deltas in inter_exp_black.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wght': (0.0, 1.0, 1.0),
                            'wdth': (0.0, 1.0, 1.0)}, deltas))

    print('  Processing composites...', flush=True)
    comp_cond = _process_composites(f, WDTH_MIN / 100.0, cond)
    comp_expand = _process_composites(f, WDTH_MAX / 100.0, expand)

    for gn, deltas in comp_cond.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (-1.0, -1.0, 0.0)}, deltas))
    for gn, deltas in comp_expand.items():
        gvar.variations.setdefault(gn, []).append(
            TupleVariation({'wdth': (0.0, 1.0, 1.0)}, deltas))

    # Composite interaction tuples: correct dot offsets at extreme weights
    comp_inter_cond_thin = _process_composites(f, WDTH_MIN / 100.0, cond_thin)
    comp_inter_exp_thin = _process_composites(f, WDTH_MAX / 100.0, exp_thin)
    comp_inter_cond_black = _process_composites(f, WDTH_MIN / 100.0, cond_black)
    comp_inter_exp_black = _process_composites(f, WDTH_MAX / 100.0, exp_black)

    for gn in comp_inter_cond_thin:
        if gn in comp_cond:
            diff = [(a[0]-b[0], a[1]-b[1]) for a, b in
                    zip(comp_inter_cond_thin[gn], comp_cond[gn])]
            if any(abs(d[0]) > 1 or abs(d[1]) > 1 for d in diff):
                gvar.variations.setdefault(gn, []).append(
                    TupleVariation({'wght': (-1.0, -1.0, 0.0),
                                    'wdth': (-1.0, -1.0, 0.0)}, diff))
    for gn in comp_inter_exp_thin:
        if gn in comp_expand:
            diff = [(a[0]-b[0], a[1]-b[1]) for a, b in
                    zip(comp_inter_exp_thin[gn], comp_expand[gn])]
            if any(abs(d[0]) > 1 or abs(d[1]) > 1 for d in diff):
                gvar.variations.setdefault(gn, []).append(
                    TupleVariation({'wght': (-1.0, -1.0, 0.0),
                                    'wdth': (0.0, 1.0, 1.0)}, diff))
    for gn in comp_inter_cond_black:
        if gn in comp_cond:
            diff = [(a[0]-b[0], a[1]-b[1]) for a, b in
                    zip(comp_inter_cond_black[gn], comp_cond[gn])]
            if any(abs(d[0]) > 1 or abs(d[1]) > 1 for d in diff):
                gvar.variations.setdefault(gn, []).append(
                    TupleVariation({'wght': (0.0, 1.0, 1.0),
                                    'wdth': (-1.0, -1.0, 0.0)}, diff))
    for gn in comp_inter_exp_black:
        if gn in comp_expand:
            diff = [(a[0]-b[0], a[1]-b[1]) for a, b in
                    zip(comp_inter_exp_black[gn], comp_expand[gn])]
            if any(abs(d[0]) > 1 or abs(d[1]) > 1 for d in diff):
                gvar.variations.setdefault(gn, []).append(
                    TupleVariation({'wght': (0.0, 1.0, 1.0),
                                    'wdth': (0.0, 1.0, 1.0)}, diff))

    comp_count = len(comp_cond)
    print(f'    {comp_count} composites ({time.time() - t0:.0f}s)', flush=True)

    _rebuild_stat(f)
    _sync_variation_tables(f)
    _strip_mac_names(f)

    f.save(out)
    print(f'  wdth axis added: simple={len(cond)} composite={comp_count} '
          f'({time.time() - t0:.0f}s total)', flush=True)


if __name__ == '__main__':
    add_wdth(sys.argv[1], sys.argv[2])


