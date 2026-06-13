# Topology-preserving width field. Centerline-derived closed form (normals
# transform by inverse-transpose, not the affine itself):
#     g  = sqrt((nx/s)^2 + ny^2)
#     dx = (s-1)*x + h*(m*(nx/s)/g - s*nx)
#     dy =           h*(m*ny/g     -   ny)
# (nx,ny)=outward unit normal, h=local half-thickness (medial radius via inward
# ray cast), s=width scale, m=stroke-weight multiplier. Self-contained; proven on
# the diagnostic glyph set before wiring into displace_v2.
import math
import os as _os
import importlib.util as _ilu

_FLAG_ON = 0x01

_sp = _ilu.spec_from_file_location(
    "_wf_off", _os.path.join(_os.path.dirname(__file__), "wdth_offset.py"))
_OFF = _ilu.module_from_spec(_sp)
_sp.loader.exec_module(_OFF)

_spf = _ilu.spec_from_file_location(
    "_wf_fair", _os.path.join(_os.path.dirname(__file__), "wdth_arch_fair.py"))
_FAIR = _ilu.module_from_spec(_spf)
_spf.loader.exec_module(_FAIR)


def _split_contours(coords, ends, flags):
    out = []
    start = 0
    for e in ends:
        pts = [(coords[start + i][0], coords[start + i][1],
                bool(flags[start + i] & _FLAG_ON), start + i)
               for i in range(e - start + 1)]
        start = e + 1
        out.append(pts)
    return out


def _segments(cont):
    n = len(cont)
    if n < 2:
        return []
    fon = next((k for k in range(n) if cont[k][2]), None)
    if fon is None:
        mids = [((cont[i][0] + cont[(i + 1) % n][0]) / 2,
                 (cont[i][1] + cont[(i + 1) % n][1]) / 2, True, -1)
                for i in range(n)]
        return [('Q', mids[i], cont[(i + 1) % n], mids[(i + 1) % n])
                for i in range(n)]
    seq = cont[fon:] + cont[:fon]
    n = len(seq)
    on_idx = [k for k in range(n) if seq[k][2]]
    segs = []
    for a in range(len(on_idx)):
        start = on_idx[a]
        end = on_idx[(a + 1) % len(on_idx)]
        offs = []
        k = (start + 1) % n
        while k != end:
            offs.append(seq[k])
            k = (k + 1) % n
        p0 = seq[start]
        p1 = seq[end]
        if not offs:
            segs.append(('L', p0, None, p1))
            continue
        nodes = [p0]
        for b in range(len(offs) - 1):
            nodes.append(((offs[b][0] + offs[b + 1][0]) / 2,
                          (offs[b][1] + offs[b + 1][1]) / 2, True, -1))
        nodes.append(p1)
        for b in range(len(offs)):
            segs.append(('Q', nodes[b], offs[b], nodes[b + 1]))
    return segs


def _q_point(p0, c, p1, t):
    mt = 1 - t
    return (mt * mt * p0[0] + 2 * mt * t * c[0] + t * t * p1[0],
            mt * mt * p0[1] + 2 * mt * t * c[1] + t * t * p1[1])


def _q_tangent(p0, c, p1, t):
    return (2 * (1 - t) * (c[0] - p0[0]) + 2 * t * (p1[0] - c[0]),
            2 * (1 - t) * (c[1] - p0[1]) + 2 * t * (p1[1] - c[1]))


def _flatten_polys(coords, ends, flags):
    g = _mk_glyph(coords, ends, flags)
    return _OFF.flatten_contours({"_wf": g}, "_wf", 0.6)


def _mk_glyph(coords, ends, flags):
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
    g = Glyph()
    g.numberOfContours = len(ends)
    g.coordinates = GlyphCoordinates([(round(x), round(y)) for x, y in coords])
    g.endPtsOfContours = list(ends)
    g.flags = bytearray(flags)
    return g


def _inside(polys, px, py):
    return _OFF._wind(polys, px, py) != 0


def _contour_outward_sign(polys, segs):
    best = None
    for kind, p0, c, p1 in segs:
        ex, ey = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(ex, ey)
        if best is None or L > best[0]:
            best = (L, (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, ex, ey)
    if best is None or best[0] < 1e-6:
        return 1.0
    _, mx, my, ex, ey = best
    L = math.hypot(ex, ey)
    tx, ty = ex / L, ey / L
    if not _inside(polys, mx + (-ty) * 1.5, my + tx * 1.5) and \
       _inside(polys, mx + ty * 1.5, my + (-tx) * 1.5):
        return 1.0
    if not _inside(polys, mx + ty * 1.5, my + (-tx) * 1.5) and \
       _inside(polys, mx + (-ty) * 1.5, my + tx * 1.5):
        return -1.0
    wl = _OFF._wind(polys, mx - ty * 1.5, my + tx * 1.5)
    wr = _OFF._wind(polys, mx + ty * 1.5, my - tx * 1.5)
    return 1.0 if abs(wl) <= abs(wr) else -1.0


def _analytic_normal(tx, ty, sign):
    L = math.hypot(tx, ty)
    if L < 1e-9:
        return None
    return (-ty / L * sign, tx / L * sign)


def _outward_normal(polys, px, py, tx, ty):
    L = math.hypot(tx, ty)
    if L < 1e-9:
        return None
    tx, ty = tx / L, ty / L
    for nx, ny in ((-ty, tx), (ty, -tx)):
        if not _inside(polys, px + nx * 1.5, py + ny * 1.5) and \
           _inside(polys, px - nx * 1.5, py - ny * 1.5):
            return (nx, ny)
    wl = _OFF._wind(polys, px - ty * 1.5, py + tx * 1.5)
    wr = _OFF._wind(polys, px + ty * 1.5, py - tx * 1.5)
    return (-ty, tx) if abs(wl) <= abs(wr) else (ty, -tx)


def _measure_h(polys, px, py, nx, ny, wg_prior, fan=(0.0, 8.0, -8.0, 16.0, -16.0)):
    cands = []
    for deg in fan:
        a = math.radians(deg)
        ca, sa = math.cos(a), math.sin(a)
        rx = -(nx * ca - ny * sa)
        ry = -(nx * sa + ny * ca)
        sx, sy = px + rx * 0.1, py + ry * 0.1
        if not _inside(polys, sx, sy):
            continue
        t = _OFF._ray_chord(polys, sx, sy, rx, ry) if hasattr(_OFF, "_ray_chord") else None
        if t is None:
            t = _chord(polys, sx, sy, rx, ry)
        if t is None:
            continue
        proj = (t + 0.1) * (rx * -nx + ry * -ny)
        if proj > 1e-3:
            cands.append(proj * 0.5)
    if not cands:
        return wg_prior * 0.5
    cands.sort()
    return cands[len(cands) // 2]


def _chord(polys, px, py, dx, dy):
    best = None
    for poly in polys:
        n = len(poly)
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            ex, ey = bx - ax, by - ay
            den = dx * (-ey) - dy * (-ex)
            if abs(den) < 1e-9:
                continue
            qx, qy = ax - px, ay - py
            t = (qx * (-ey) - qy * (-ex)) / den
            u = (dx * qy - dy * qx) / den
            if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9:
                if best is None or t < best:
                    best = t
    return best


def _displace(x, y, nx, ny, h, s, m):
    g = math.sqrt((nx / s) ** 2 + ny ** 2)
    if g < 1e-9:
        return (x * s, y)
    qx = x * s + h * (m * (nx / s) / g - s * nx)
    qy = y + h * (m * ny / g - ny)
    return (qx, qy)


def _seg_tan_start(seg):
    kind, p0, c, p1 = seg
    if kind == 'L':
        return (p1[0] - p0[0], p1[1] - p0[1])
    return (2 * (c[0] - p0[0]), 2 * (c[1] - p0[1]))


def _seg_tan_end(seg):
    kind, p0, c, p1 = seg
    if kind == 'L':
        return (p1[0] - p0[0], p1[1] - p0[1])
    return (2 * (p1[0] - c[0]), 2 * (p1[1] - c[1]))


def _norm(v):
    L = math.hypot(v[0], v[1])
    return (v[0] / L, v[1] / L) if L > 1e-9 else (0.0, 0.0)


def _ang_between(a, b):
    da = math.atan2(a[1], a[0])
    db = math.atan2(b[1], b[0])
    return abs(((db - da + math.pi) % (2 * math.pi)) - math.pi)


def _line_isect(a0, da, b0, db):
    den = da[0] * (-db[1]) - da[1] * (-db[0])
    if abs(den) < 1e-9:
        return None
    qx, qy = b0[0] - a0[0], b0[1] - a0[1]
    u = (qx * (-db[1]) - qy * (-db[0])) / den
    return (a0[0] + u * da[0], a0[1] + u * da[1])


def _recon_offcurve(p0, c, p1, q0, q1):
    a = (c[0] - p0[0], c[1] - p0[1])
    b = (p1[0] - c[0], p1[1] - c[1])
    la, lb = math.hypot(*a), math.hypot(*b)
    d = math.hypot(q1[0] - q0[0], q1[1] - q0[1])
    if la < 1e-6 or lb < 1e-6 or d < 1e-9:
        return (0.5 * (q0[0] + q1[0]), 0.5 * (q0[1] + q1[1]))
    t0 = (a[0] / la, a[1] / la)
    t1 = (b[0] / lb, b[1] / lb)
    if abs(t0[0] * t1[1] - t0[1] * t1[0]) < 1e-3:
        h0, h1 = min(la, 3.0 * d), min(lb, 3.0 * d)
        c0 = (q0[0] + h0 * t0[0], q0[1] + h0 * t0[1])
        c1 = (q1[0] - h1 * t1[0], q1[1] - h1 * t1[1])
        return (0.5 * (c0[0] + c1[0]), 0.5 * (c0[1] + c1[1]))
    cp = _line_isect(q0, t0, q1, (-t1[0], -t1[1]))
    if (cp is None
            or math.hypot(cp[0] - q0[0], cp[1] - q0[1]) > 4 * d
            or math.hypot(cp[0] - q1[0], cp[1] - q1[1]) > 4 * d):
        h0, h1 = min(la, 3.0 * d), min(lb, 3.0 * d)
        c0 = (q0[0] + h0 * t0[0], q0[1] + h0 * t0[1])
        c1 = (q1[0] - h1 * t1[0], q1[1] - h1 * t1[1])
        return (0.5 * (c0[0] + c1[0]), 0.5 * (c0[1] + c1[1]))
    return cp


_CORNER_DEG = 32.0
_MITER = 4.0
_CONST_H = True
_CAP_EDGE_FRAC = 0.25
_CAP_REVERSAL_EPS = 1.0
_WALL_MIN_LEN = 120.0
_CAP_MAX_LEN = 40.0
_CAP_ANCHOR_TOL = 2.0
_CAP_TAPER_LEN = 200.0


def _smoother_falloff(t):
    if t <= 0.0:
        return 1.0
    if t >= 1.0:
        return 0.0
    return 1.0 - (10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5)


def _is_arch_stem_cap(segs, i, j):
    # The short-L-between-two-corners pattern is ambiguous: it is a terminal cap
    # (both flanks straight stroke-sides -> repair safely translates it) OR an
    # arch-to-stem junction (a/b/d/g/p/q: one flank the curved arch Q, the other a
    # long straight stem wall L). Repairing the latter shears the wall off-vertical
    # and pinches a notch. Discriminate by: short cap edge (a structural ledge, not
    # a stroke) flanked by a curve on one side and a long straight stem wall.
    n = len(segs)
    cap = segs[i]
    clen = math.hypot(cap[3][0] - cap[1][0], cap[3][1] - cap[1][1])
    if clen > _CAP_MAX_LEN:
        return False
    prev_seg = segs[(i - 1) % n]
    next_seg = segs[j]
    kinds = (prev_seg[0], next_seg[0])
    if 'Q' not in kinds or 'L' not in kinds:
        return False
    wall = prev_seg if prev_seg[0] == 'L' else next_seg
    wlen = math.hypot(wall[3][0] - wall[1][0], wall[3][1] - wall[1][1])
    return wlen >= _WALL_MIN_LEN


def _repair_cap_edges(segs, verts, corner, vtarget, hsmooth_v, sign, wg, s, m):
    # Two corners sharing one short straight edge get miters from different
    # segment pairs, so the joins can invert the edge and pinch a notch. Detect
    # inversion along the edge's OWN transformed tangent (not x-order, which is
    # axis-specific) and, when the edge collapses or reverses, hand both
    # endpoints to the edge: displace them along the shared edge normal so the
    # cap is preserved as a unit. Order-preserving, local, and only fires where
    # the independent miters are already geometrically invalid.
    n = len(segs)
    for i in range(n):
        if segs[i][0] != 'L':
            continue
        j = (i + 1) % n
        if not (corner[i] and corner[j]):
            continue
        if _is_arch_stem_cap(segs, i, j):
            continue
        ax, ay = verts[i][0], verts[i][1]
        bx, by = verts[j][0], verts[j][1]
        elen = math.hypot(bx - ax, by - ay)
        if elen < 1e-6:
            continue
        nE = _analytic_normal(bx - ax, by - ay, sign)
        if nE is None:
            continue
        hv = 0.5 * (hsmooth_v.get(i, wg * 0.5) + hsmooth_v.get(j, wg * 0.5))
        A = _displace(ax, ay, nE[0], nE[1], hv, s, m)
        B = _displace(bx, by, nE[0], nE[1], hv, s, m)
        ux, uy = B[0] - A[0], B[1] - A[1]
        canon = math.hypot(ux, uy)
        if canon < 1e-6:
            continue
        ux, uy = ux / canon, uy / canon
        qi = vtarget[i]
        qj = vtarget[j]
        signed = (qj[0] - qi[0]) * ux + (qj[1] - qi[1]) * uy
        reversed_join = signed <= _CAP_REVERSAL_EPS
        near_collapse = elen < _CAP_EDGE_FRAC * hv and signed < _CAP_EDGE_FRAC * canon
        if reversed_join or near_collapse:
            vtarget[i] = A
            vtarget[j] = B


def _arch_nodes(segs, verts, corner, A, fwd, n, steps=6):
    nodes = []
    for k in range(steps):
        idx = (A + k) % n if fwd else (A - 1 - k) % n
        sg = segs[idx]
        if sg[0] != 'Q':
            break
        c = sg[2]
        nodes.append((False, None, c[3] if c else -1, (c[0], c[1]) if c else None))
        vk = (A + k + 1) % n if fwd else (A - 1 - k) % n
        nodes.append((True, vk, verts[vk][3], (verts[vk][0], verts[vk][1])))
        if corner[vk]:
            break
    return nodes


def _anchor_arch_caps(segs, verts, corner, vtarget, s):
    # Structural-join model for bowl/arch-to-stem caps. The stem wall is the
    # dominant feature: keep its endpoint on the wall line (set by the miter, not
    # the cap). The short cap is structural joinery: preserve its base vector under
    # the anisotropic scale (s,1) so the curve starts where the scaled ledge ends.
    # Move the arch on-curve to that anchored point and translate the first arch
    # quadratic rigidly (control + next on-curve by the same Delta) to keep its
    # start tangent and curvature, then taper Delta to zero over the bowl with a C2
    # smoothstep so no curvature artifact is introduced downstream.
    n = len(segs)
    ctrl_corr = {}
    for i in range(n):
        if segs[i][0] != 'L':
            continue
        j = (i + 1) % n
        if not (corner[i] and corner[j]):
            continue
        if not _is_arch_stem_cap(segs, i, j):
            continue
        fwd = segs[(i - 1) % n][0] == 'L'
        W, A = (i, j) if fwd else (j, i)
        capx = verts[A][0] - verts[W][0]
        capy = verts[A][1] - verts[W][1]
        Wt = vtarget[W]
        An = vtarget[A]
        a_struct = (Wt[0] + s * capx, Wt[1] + capy)
        dlt = (a_struct[0] - An[0], a_struct[1] - An[1])
        if abs(dlt[0]) < _CAP_ANCHOR_TOL and abs(dlt[1]) < _CAP_ANCHOR_TOL:
            continue
        vtarget[A] = a_struct
        nodes = _arch_nodes(segs, verts, corner, A, fwd, n)
        prev_xy = (verts[A][0], verts[A][1])
        d_accum = 0.0
        d_ref = 0.0
        for idx_node, (is_onc, vk, ref, bxy) in enumerate(nodes):
            if bxy is None:
                continue
            d_accum += math.hypot(bxy[0] - prev_xy[0], bxy[1] - prev_xy[1])
            prev_xy = bxy
            if idx_node <= 1:
                factor = 1.0
                if idx_node == 1:
                    d_ref = d_accum
            else:
                factor = _smoother_falloff((d_accum - d_ref) / _CAP_TAPER_LEN)
            if factor <= 0.0:
                break
            cdx, cdy = dlt[0] * factor, dlt[1] * factor
            if is_onc and vk is not None:
                vtarget[vk] = (vtarget[vk][0] + cdx, vtarget[vk][1] + cdy)
            elif ref is not None and ref >= 0:
                ctrl_corr[ref] = (cdx, cdy)
    return ctrl_corr


def field_deltas(coords, ends, flags, wg, s, m):
    polys = _flatten_polys(coords, ends, flags)
    conts = _split_contours(coords, ends, flags)
    out = {}
    for cont in conts:
        _contour_field(polys, cont, wg, s, m, out)
    _FAIR.fair_arches(coords, ends, flags, out, s)
    return out


def _contour_field(polys, cont, wg, s, m, out):
    segs = _segments(cont)
    n = len(segs)
    if n < 2:
        return
    verts = [segs[i][1] for i in range(n)]
    tin = [_seg_tan_end(segs[(i - 1) % n]) for i in range(n)]
    tout = [_seg_tan_start(segs[i]) for i in range(n)]
    corner = [_ang_between(tin[i], tout[i]) > math.radians(_CORNER_DEG)
              for i in range(n)]
    sign = _contour_outward_sign(polys, segs)

    stations = []
    for i in range(n):
        vx, vy = verts[i][0], verts[i][1]
        if corner[i]:
            tcomb = tout[i]
        else:
            tc, td = _norm(tin[i]), _norm(tout[i])
            tcomb = (tc[0] + td[0], tc[1] + td[1])
            if math.hypot(*tcomb) < 1e-6:
                tcomb = tout[i]
        nrm = _analytic_normal(tcomb[0], tcomb[1], sign)
        rh = wg * 0.5 if _CONST_H else (_measure_h(polys, vx, vy, nrm[0], nrm[1], wg) if nrm else wg * 0.5)
        stations.append({'p': (vx, vy), 'n': nrm, 'h': rh, 'corner': corner[i],
                         'kind': 'v', 'i': i})
        if segs[i][0] == 'Q':
            p0, c, p1 = segs[i][1], segs[i][2], segs[i][3]
            for t in (0.25, 0.5, 0.75):
                pt = _q_point(p0, c, p1, t)
                tan = _q_tangent(p0, c, p1, t)
                nm = _analytic_normal(tan[0], tan[1], sign)
                hh = wg * 0.5 if _CONST_H else (_measure_h(polys, pt[0], pt[1], nm[0], nm[1], wg) if nm else wg * 0.5)
                stations.append({'p': pt, 'n': nm, 'h': hh, 'corner': False,
                                 'kind': 'm', 'seg': i, 't': t})

    _smooth_h(stations)

    hsmooth_v = {}
    seg_h = {}
    for st in stations:
        if st['kind'] == 'v':
            hsmooth_v[st['i']] = st['h']
        else:
            seg_h.setdefault(st['seg'], {})[st['t']] = st['h']

    vtarget = [None] * n
    for i in range(n):
        vx, vy = verts[i][0], verts[i][1]
        if corner[i]:
            nA = _analytic_normal(tin[i][0], tin[i][1], sign)
            nB = _analytic_normal(tout[i][0], tout[i][1], sign)
            hv = hsmooth_v.get(i, wg * 0.5)
            if nA is None or nB is None:
                nrm = nA or nB
                vtarget[i] = _displace(vx, vy, nrm[0], nrm[1], hv, s, m) if nrm else (vx * s, vy)
                continue
            A0 = _displace(vx, vy, nA[0], nA[1], hv, s, m)
            B0 = _displace(vx, vy, nB[0], nB[1], hv, s, m)
            dA = _norm((s * tin[i][0], tin[i][1]))
            dB = _norm((s * tout[i][0], tout[i][1]))
            I = _line_isect(A0, dA, B0, dB)
            mid = ((A0[0] + B0[0]) / 2, (A0[1] + B0[1]) / 2)
            if I is None or math.hypot(I[0] - mid[0], I[1] - mid[1]) > _MITER * max(hv, 1.0):
                vtarget[i] = mid
            else:
                vtarget[i] = I
        else:
            st_n = next((st['n'] for st in stations
                         if st['kind'] == 'v' and st['i'] == i), None)
            hv = hsmooth_v.get(i, wg * 0.5)
            if st_n is None:
                vtarget[i] = (vx * s, vy)
            else:
                vtarget[i] = _displace(vx, vy, st_n[0], st_n[1], hv, s, m)

    _repair_cap_edges(segs, verts, corner, vtarget, hsmooth_v, sign, wg, s, m)
    ctrl_corr = _anchor_arch_caps(segs, verts, corner, vtarget, s)

    for i in range(n):
        ref = verts[i][3]
        if ref >= 0:
            out[ref] = (vtarget[i][0] - verts[i][0], vtarget[i][1] - verts[i][1])

    # Off-curve controls: parallel-normal offset. Each raw off-curve owns one
    # quadratic segment; displace it by that segment's outward normal (chord
    # tangent p1-p0, fallback to t=0.5 tangent if chord degenerate). This is the
    # correct parallel-offset discretization and preserves G2; reconstructing
    # controls from scaled source tangents destroys curvature at the extrema.
    for i in range(n):
        seg = segs[i]
        if seg[0] != 'Q' or seg[2] is None or seg[2][3] < 0:
            continue
        c = seg[2]
        if segs[(i - 1) % n][0] == 'L' or segs[(i + 1) % n][0] == 'L':
            q0 = vtarget[i]
            q1 = vtarget[(i + 1) % n]
            cp = _recon_offcurve(seg[1], c, seg[3], q0, q1)
            cc = ctrl_corr.get(c[3], (0.0, 0.0))
            out[c[3]] = (cp[0] - c[0] + cc[0], cp[1] - c[1] + cc[1])
            continue
        chord = (seg[3][0] - seg[1][0], seg[3][1] - seg[1][1])
        if math.hypot(*chord) < 1e-6:
            chord = _q_tangent(seg[1], seg[2], seg[3], 0.5)
        nrm = _analytic_normal(chord[0], chord[1], sign)
        if nrm is None:
            hv = hsmooth_v.get(i, wg * 0.5)
            cc = ctrl_corr.get(c[3], (0.0, 0.0))
            out[c[3]] = (c[0] * s - c[0] + cc[0], cc[1])
            continue
        hc = seg_h.get(i, {}).get(0.5, wg * 0.5)
        q = _displace(c[0], c[1], nrm[0], nrm[1], hc, s, m)
        cc = ctrl_corr.get(c[3], (0.0, 0.0))
        out[c[3]] = (q[0] - c[0] + cc[0], q[1] - c[1] + cc[1])



def _smooth_h(stations):
    n = len(stations)
    if n < 3:
        return
    raw = [st['h'] for st in stations]
    sm = list(raw)
    for i in range(n):
        if stations[i]['corner']:
            continue
        win = [raw[i]]
        for off in (1, 2):
            j = (i - off) % n
            if any(stations[(i - k) % n]['corner'] for k in range(1, off + 1)):
                break
            win.append(raw[j])
        for off in (1, 2):
            j = (i + off) % n
            if any(stations[(i + k) % n]['corner'] for k in range(1, off + 1)):
                break
            win.append(raw[j])
        win.sort()
        med = win[len(win) // 2]
        sm[i] = 0.5 * raw[i] + 0.5 * med
    for i in range(n):
        stations[i]['h'] = sm[i]


def _curve_sample_h(polys, p0, c, p1, t, h, s, m):
    pt = _q_point(p0, c, p1, t)
    tan = _q_tangent(p0, c, p1, t)
    nrm = _outward_normal(polys, pt[0], pt[1], tan[0], tan[1])
    if nrm is None:
        return None
    return _displace(pt[0], pt[1], nrm[0], nrm[1], h, s, m)


def _curve_sample_fixed(p0, c, p1, t, h, s, m, ref):
    pt = _q_point(p0, c, p1, t)
    tx, ty = _q_tangent(p0, c, p1, t)
    L = math.hypot(tx, ty)
    if L < 1e-9:
        return None
    tx, ty = tx / L, ty / L
    nx, ny = -ty, tx
    if nx * ref[0] + ny * ref[1] < 0:
        nx, ny = ty, -tx
    return _displace(pt[0], pt[1], nx, ny, h, s, m)


def _curve_sample(polys, p0, c, p1, t, wg, s, m):
    pt = _q_point(p0, c, p1, t)
    tan = _q_tangent(p0, c, p1, t)
    nrm = _outward_normal(polys, pt[0], pt[1], tan[0], tan[1])
    if nrm is None:
        return None
    h = _measure_h(polys, pt[0], pt[1], nrm[0], nrm[1], wg)
    return _displace(pt[0], pt[1], nrm[0], nrm[1], h, s, m)

