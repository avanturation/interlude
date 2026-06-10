import math

_SELF_X_TOL = 2
_FLAG_ON_CURVE = 0x01
_DSD_MAX_YDEV_RATIO = 0.10
_DSD_MAX_YDEV_FLOOR = 6.0
_DSD_MIN_VSTEM_WIDTH_RATIO = 0.6

import os as _os2, importlib.util as _ilu2
_ds = _ilu2.spec_from_file_location("wdth_diagonal", _os2.path.join(_os2.path.dirname(__file__), "wdth_diagonal.py"))
_DIAG = _ilu2.module_from_spec(_ds)
_ds.loader.exec_module(_DIAG)

def _wind(polys, px, py):
    w=0
    for poly in polys:
        n=len(poly)
        for i in range(n):
            x1,y1=poly[i];x2,y2=poly[(i+1)%n]
            if y1<=py:
                if y2>py and ((x2-x1)*(py-y1)-(px-x1)*(y2-y1))>0:w+=1
            else:
                if y2<=py and ((x2-x1)*(py-y1)-(px-x1)*(y2-y1))<0:w-=1
    return w

def _contours_xy(coords, ends):
    out=[];start=0
    for e in ends:
        out.append([(coords[start+i][0],coords[start+i][1]) for i in range(e-start+1)])
        start=e+1
    return out

def _edge_normal_x(poly_scaled, allpolys_scaled, i, probe=2.0):
    n=len(poly_scaled)
    x1,y1=poly_scaled[i];x2,y2=poly_scaled[(i+1)%n]
    ex,ey=x2-x1,y2-y1;L=math.hypot(ex,ey)
    if L<1e-6:return None
    tx,ty=ex/L,ey/L
    lx,ly=-ty,tx;rx,ry=ty,-tx
    mx,my=(x1+x2)/2,(y1+y2)/2
    wl=_wind(allpolys_scaled,mx+lx*probe,my+ly*probe)
    wr=_wind(allpolys_scaled,mx+rx*probe,my+ry*probe)
    if wl==0 and wr!=0:return lx
    if wr==0 and wl!=0:return rx
    return lx if abs(wl)<=abs(wr) else rx

def _vertical_edge_unit_nx(poly_scaled, allpolys_scaled, i, min_len=8.0, max_abs_dx=3.0, min_verticalness=0.92):
    n=len(poly_scaled)
    x1,y1=poly_scaled[i];x2,y2=poly_scaled[(i+1)%n]
    ex,ey=x2-x1,y2-y1;L=math.hypot(ex,ey)
    if L<1e-6 or L<min_len:return None
    if abs(ex)>max_abs_dx and abs(ey)/L<min_verticalness:return None
    if abs(ey)/L<min_verticalness:return None
    raw=_edge_normal_x(poly_scaled,allpolys_scaled,i)
    if raw is None or abs(raw)<1e-6:return None
    return 1.0 if raw>0 else -1.0

def _stem_cap_bridge(cont, allpolys, idx):
    # A short horizontal cap that connects to a vertical stem edge (e.g. g's stem-top
    # cap meeting the bowl) must move WITH the stem, not average stem(-1) and bowl(+0.x)
    # which splays the corner and kinks the bowl entry. If this point is one end of a
    # short near-horizontal edge whose other end has a vertical stem edge (nx=+-1),
    # inherit that stem sign so the cap translates rigidly with the stem.
    n = len(cont)
    for nb in ((idx + 1) % n, (idx - 1) % n):
        ax, ay = cont[idx]
        bx, by = cont[nb]
        dx = bx - ax
        dy = by - ay
        L = math.hypot(dx, dy)
        if L < 8.0 or L > 100.0:
            continue
        if abs(dx) < 1e-6 or abs(dy) / L > 0.18:
            continue
        for e in ((nb - 1) % n, nb):
            v = _vertical_edge_unit_nx(cont, allpolys, e)
            if v is not None:
                return v
    return None


def _pt_normal_x(cont_scaled, allpolys_scaled, idx):
    n=len(cont_scaled)
    prev_i=(idx-1)%n
    v_prev=_vertical_edge_unit_nx(cont_scaled,allpolys_scaled,prev_i)
    v_cur=_vertical_edge_unit_nx(cont_scaled,allpolys_scaled,idx)
    verticals=[v for v in (v_prev,v_cur) if v is not None]
    if verticals:
        if all(v>0 for v in verticals):return 1.0
        if all(v<0 for v in verticals):return -1.0
    bridge=_stem_cap_bridge(cont_scaled,allpolys_scaled,idx)
    if bridge is not None:
        return bridge
    nx_prev=_edge_normal_x(cont_scaled,allpolys_scaled,prev_i)
    nx_cur=_edge_normal_x(cont_scaled,allpolys_scaled,idx)
    vals=[v for v in (nx_prev,nx_cur) if v is not None]
    if not vals:return 0.0
    return sum(vals)/len(vals)


def _curve_aware_nx(conts, scaled, flags, ends):
    # Per-point outward-normal-x for the condensation field. On-curve points use the
    # edge-normal logic (which snaps vertical stem edges to +-1 so stem thickness is
    # restored). Off-curve control points must NOT use their own control-polygon edge
    # normal: it differs from the curve's true normal, so adjacent points get
    # different nx, distorting the control polygon and kinking the Bezier (f hook, y
    # tail, g bowl). Instead an off-curve control takes its nx from the surrounding
    # on-curve anchors (ordinal lerp) so the whole curve segment scales coherently.
    starts = []
    st = 0
    for e in ends:
        starts.append(st)
        st = e + 1
    out = []
    for ci, cont in enumerate(scaled):
        n = len(cont)
        base0 = starts[ci]
        on = [bool(flags[base0 + i] & _FLAG_ON_CURVE) for i in range(n)]
        nx = [0.0] * n
        any_on = any(on)
        for i in range(n):
            if on[i] or not any_on:
                nx[i] = _pt_normal_x(cont, scaled, i)
        for i in range(n):
            if on[i] or not any_on:
                continue
            prev_on = (i - 1) % n
            steps_p = 1
            while not on[prev_on]:
                prev_on = (prev_on - 1) % n
                steps_p += 1
            next_on = (i + 1) % n
            steps_n = 1
            while not on[next_on]:
                next_on = (next_on + 1) % n
                steps_n += 1
            total = steps_p + steps_n
            t = steps_p / total
            nx[i] = (1.0 - t) * nx[prev_on] + t * nx[next_on]
        out.append(nx)
    return out


def _contour_orientation(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return 1.0 if a > 0 else -1.0


def _long_vertical_edges(conts, scaled, min_len=180.0, min_vert=0.92, max_dx=6.0):
    edges = []
    for ci, cont in enumerate(conts):
        n = len(cont)
        for i in range(n):
            x1, y1 = cont[i]
            x2, y2 = cont[(i + 1) % n]
            ex, ey = x2 - x1, y2 - y1
            L = math.hypot(ex, ey)
            if L < min_len or abs(ey) / L < min_vert or abs(ex) > max_dx:
                continue
            sgn = _vertical_edge_unit_nx(scaled[ci], scaled, i, min_len=8.0)
            if sgn is None:
                continue
            edges.append(((x1 + x2) / 2.0, min(y1, y2), max(y1, y2), sgn))
    return edges


def _is_diagonal(dx, dy, lo=20.0, hi=70.0):
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return False
    ang = abs(math.degrees(math.atan2(abs(dy), abs(dx))))
    return lo <= ang <= hi


def _junction_anchors(conts, scaled, oncurve=None, max_anchor_dist=None, min_diag=200.0):
    vedges = _long_vertical_edges(conts, scaled)
    out = []
    for ci, cont in enumerate(conts):
        ori = _contour_orientation(cont)
        n = len(cont)
        row = [None] * n
        oc = oncurve[ci] if oncurve is not None else None
        if vedges:
            for i in range(n):
                if oc is not None and not (oc[i] and oc[(i - 1) % n] and oc[(i + 1) % n]):
                    continue
                px, py = cont[(i - 1) % n]
                x, y = cont[i]
                nx2, ny2 = cont[(i + 1) % n]
                e1 = (x - px, y - py)
                e2 = (nx2 - x, ny2 - y)
                cross = e1[0] * e2[1] - e1[1] * e2[0]
                if cross * ori >= 0:
                    continue
                l1 = math.hypot(*e1)
                l2 = math.hypot(*e2)
                d1 = _is_diagonal(*e1)
                d2 = _is_diagonal(*e2)
                if not ((d1 and l1 >= min_diag) or (d2 and l2 >= min_diag)):
                    continue
                best = None
                for (xb, ylo, yhi, sgn) in vedges:
                    if y < ylo - 2 or y > yhi + 2:
                        continue
                    dx = abs(x - xb)
                    if max_anchor_dist is not None and dx > max_anchor_dist:
                        continue
                    if best is None or dx < best[0]:
                        best = (dx, xb, sgn)
                if best is not None:
                    row[i] = (best[1], best[2])
        out.append(row)
    return out


def condense_glyph_points(glyf, gn, s, W, floor=18.0):
    g=glyf[gn]
    if g.numberOfContours<=0:
        return None
    g.expand(glyf)
    coords=[(x,y) for x,y in g.coordinates]
    ends=list(g.endPtsOfContours)
    flags=list(g.flags)
    delta=W*(1.0-s)/2.0
    conts=_contours_xy(coords,ends)
    scaled=[[(x*s,y) for x,y in c] for c in conts]
    new=[]
    start=0
    for ci,cont in enumerate(scaled):
        m=len(cont)
        for i in range(m):
            x,y=cont[i]
            nx=_pt_normal_x(cont,scaled,i)
            new.append((x+delta*nx, y))
    out=[(round(x),round(y)) for x,y in new]
    return out,ends,flags

def apply_to_glyph(glyf, gn, s, W, hmtx=None, floor=18.0):
    res=condense_glyph_points(glyf,gn,s,W,floor)
    if res is None:return False
    pts,ends,flags=res
    g=glyf[gn]
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    g.coordinates=GlyphCoordinates(pts)
    g.endPtsOfContours=list(ends)
    g.flags=bytearray(flags)
    return True

def _count_self_x(pts, ends, flags):
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
    g=Glyph();g.numberOfContours=len(ends)
    g.coordinates=GlyphCoordinates(pts);g.endPtsOfContours=list(ends)
    g.flags=bytearray(flags)
    polys=_OL.flatten_contours({_FK:g},_FK,0.6)
    def ccw(a,b,c):return (c[1]-a[1])*(b[0]-a[0])-(b[1]-a[1])*(c[0]-a[0])
    def sx(a1,a2,b1,b2):
        d1=ccw(b1,b2,a1);d2=ccw(b1,b2,a2);d3=ccw(a1,a2,b1);d4=ccw(a1,a2,b2)
        return (d1*d2<0)and(d3*d4<0)
    tot=0
    for poly in polys:
        n=len(poly)
        if n<3:continue
        seg=[(poly[i],poly[(i+1)%n]) for i in range(n)]
        bb=[(min(a[0],b[0]),max(a[0],b[0]),min(a[1],b[1]),max(a[1],b[1])) for a,b in seg]
        for i in range(n):
            ax0,ax1,ay0,ay1=bb[i]
            a1,a2=seg[i]
            for j in range(i+2,n):
                if i==0 and j==n-1:continue
                bx0,bx1,by0,by1=bb[j]
                if bx0>ax1 or bx1<ax0 or by0>ay1 or by1<ay0:continue
                b1,b2=seg[j]
                if sx(a1,a2,b1,b2):tot+=1
    return tot

_FK="_dispcheck"
import os as _os, importlib.util as _ilu
_ols=_ilu.spec_from_file_location("_ol",_os.path.join(_os.path.dirname(__file__),"wdth_offset.py"))
_OL=_ilu.module_from_spec(_ols);_ols.loader.exec_module(_OL)

def _flatten_raw(raw):
    n=len(raw)
    pts=[]
    for i in range(n):
        cur=raw[i];nxt=raw[(i+1)%n]
        pts.append(cur)
        if (not cur[2]) and (not nxt[2]):
            pts.append(((cur[0]+nxt[0])/2,(cur[1]+nxt[1])/2,True))
    m=len(pts)
    foi=next((k for k in range(m) if pts[k][2]),None)
    if foi is None:return []
    seq=pts[foi:]+pts[:foi];m=len(seq)
    out=[];k=0
    while k<m:
        x,y,on=seq[k];out.append((x,y))
        nx,ny,non=seq[(k+1)%m]
        if not non:
            ex,ey,_=seq[(k+2)%m]
            for t in (0.25,0.5,0.75):
                bx=(1-t)**2*x+2*(1-t)*t*nx+t*t*ex
                by=(1-t)**2*y+2*(1-t)*t*ny+t*t*ey
                out.append((bx,by))
            k+=2
        else:k+=1
    return out

def condense_safe(glyf, gn, s, W, floor=18.0):
    g=glyf[gn]
    if g.numberOfContours<=0:return None
    g.expand(glyf)
    base=[(x,y) for x,y in g.coordinates]
    ends=list(g.endPtsOfContours);flags=list(g.flags)
    conts=_contours_xy(base,ends)
    scaled=[[(x*s,y) for x,y in c] for c in conts]
    nxs=[]
    for cont in scaled:
        m=len(cont)
        nxs.append([_pt_normal_x(cont,scaled,i) for i in range(m)])
    o_self=_count_self_x([(round(x*s),round(y)) for x,y in base],ends,flags)
    last=None
    for kfac in (1.0,0.9,0.8,0.7,0.6,0.5,0.4,0.3,0.2,0.1,0.0):
        delta=W*(1.0-s)/2.0*kfac
        new=[]
        for ci,cont in enumerate(scaled):
            for i,(x,y) in enumerate(cont):
                new.append((x+delta*nxs[ci][i], y))
        rnd=[(round(x),round(y)) for x,y in new]
        last=rnd
        if _count_self_x(rnd,ends,flags)<=o_self:
            return rnd,ends,flags,kfac
    return last,ends,flags,0.0


_MU = None


def _mult_mod():
    global _MU
    if _MU is None:
        import os as __os, importlib.util as __ilu
        sp = __ilu.spec_from_file_location("_mu", __os.path.join(__os.path.dirname(__file__), "wdth_multipliers.py"))
        _MU = __ilu.module_from_spec(sp)
        sp.loader.exec_module(_MU)
    return _MU


_ST = None


def _stems_mod():
    global _ST
    if _ST is None:
        import os as __os, importlib.util as __ilu
        sp = __ilu.spec_from_file_location("_st", __os.path.join(__os.path.dirname(__file__), "wdth_stems.py"))
        _ST = __ilu.module_from_spec(sp)
        sp.loader.exec_module(_ST)
    return _ST


def _measure_coords(coords, ends, flags):
    return _stems_mod().measure_stem({"_m": _mk_glyph(coords, ends, flags)}, "_m")


def _mk_glyph(coords, ends, flags):
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
    g = Glyph()
    g.numberOfContours = len(ends)
    g.coordinates = GlyphCoordinates([(round(x), round(y)) for x, y in coords])
    g.endPtsOfContours = list(ends)
    g.flags = bytearray(flags)
    return g


def _solve_lambda(measure_at, target, tol=2.0, lam_cap=5.0, step=0.125):
    cache = {}
    best = [None]

    def ev(lam):
        lam = max(0.0, min(lam_cap, lam))
        key = round(lam, 6)
        if key in cache:
            return cache[key]
        m = measure_at(lam)
        cache[key] = m
        if m is not None:
            err = abs(m - target)
            if best[0] is None or err < best[0][0] or (err == best[0][0] and lam < best[0][1]):
                best[0] = (err, lam, m)
        return m

    def sample(a, b):
        pts = []
        n = int(round((b - a) / step))
        for i in range(n + 1):
            lam = a + i * step
            pts.append((lam, ev(lam)))
        return pts

    def refine(left, right, iters=10):
        lo_lam, lo_m = left
        hi_lam, hi_m = right
        if lo_m is None or hi_m is None:
            return
        lo_d = lo_m - target
        hi_d = hi_m - target
        if abs(lo_d) <= tol or abs(hi_d) <= tol:
            return
        if lo_d == 0 or hi_d == 0 or lo_d * hi_d > 0:
            return
        for _ in range(iters):
            mid_lam = (lo_lam + hi_lam) / 2.0
            mid_m = ev(mid_lam)
            if mid_m is None:
                return
            mid_d = mid_m - target
            if abs(mid_d) <= tol:
                return
            if lo_d * mid_d <= 0:
                hi_lam, hi_d = mid_lam, mid_d
            else:
                lo_lam, lo_d = mid_lam, mid_d

    def refine_all(samples):
        s = sorted(samples, key=lambda x: x[0])
        for i in range(len(s) - 1):
            a, b = s[i], s[i + 1]
            if a[1] is None or b[1] is None:
                continue
            da, db = a[1] - target, b[1] - target
            if abs(da) <= tol or abs(db) <= tol or da * db <= 0:
                refine(a, b)

    def within_tol():
        cands = [(float(k), abs(m - target)) for k, m in cache.items() if m is not None and abs(m - target) <= tol]
        if not cands:
            return None
        cands.sort(key=lambda x: (x[0], x[1]))
        return cands[0][0]

    def zoom(rounds=2, points=9, radius=step):
        for _ in range(rounds):
            if best[0] is None:
                return
            center = best[0][1]
            a = max(0.0, center - radius)
            b = min(lam_cap, center + radius)
            if b <= a:
                return
            for i in range(points):
                ev(a + (b - a) * i / (points - 1))
            radius /= 4.0

    refine_all(sample(0.0, 3.0))
    hit = within_tol()
    if hit is not None:
        return hit

    m3 = ev(3.0)
    m2875 = ev(2.875)
    if best[0] is not None and abs(best[0][1] - 3.0) < 1e-6 and m3 is not None and m2875 is not None and abs(m3 - target) < abs(m2875 - target):
        refine_all(sample(3.0, lam_cap))
        hit = within_tol()
        if hit is not None:
            return hit

    zoom()
    if best[0] is not None:
        return best[0][1]
    return 1.0


def displace_v2(glyf, gn, s, Wg, mult, do_guard=True, baseline_self=None, allow_anchor=False, allow_diag=False):
    g = glyf[gn]
    if g.numberOfContours <= 0:
        return None
    g.expand(glyf)
    base = [(x, y) for x, y in g.coordinates]
    ends = list(g.endPtsOfContours)
    flags = list(g.flags)
    conts = _contours_xy(base, ends)

    scaled_s = [[(x * s, y) for x, y in c] for c in conts]
    nxs = _curve_aware_nx(conts, scaled_s, flags, ends)
    if allow_anchor:
        oc = []
        start = 0
        for e in ends:
            oc.append([bool(flags[k] & _FLAG_ON_CURVE) for k in range(start, e + 1)])
            start = e + 1
        anchors = _junction_anchors(conts, scaled_s, oncurve=oc)
    else:
        anchors = [[None] * len(c) for c in conts]

    full_delta = (mult - s) * Wg / 2.0

    if allow_diag:
        claimed = _DIAG.claim_diagonal_points(base, ends, flags, Wg)
        dsd = _DIAG.diagonal_stroke_deltas(base, ends, flags, Wg, s, mult) if abs(s - 1.0) > 1e-6 else {}
    else:
        claimed = set()
        dsd = {}

    if dsd:
        def _claimed_coords(use_dsd):
            out = []
            gi = 0
            for cont in conts:
                for x, y in cont:
                    if use_dsd and gi in dsd:
                        out.append(dsd[gi])
                    else:
                        out.append((x * s, y))
                    gi += 1
            return [(round(x), round(y)) for x, y in out]
        affine_self = _count_self_x(_claimed_coords(False), ends, flags)
        perstroke_self = _count_self_x(_claimed_coords(True), ends, flags)
        # Crossing-stroke glyphs (x, X, y at expansion) genuinely self-intersect, so a
        # per-stroke affine can transiently raise the self-x count above plain uniform
        # scaling without being degenerate. Comparing against affine_self alone false-
        # positives there and discards a kink-free dsd, forcing the nx fallback which
        # kinks the diagonal tips (x tips 0deg->8deg at wd125). Allow the glyph's
        # inherent crossing budget plus tolerance; a real needle/spike still exceeds it.
        base_self = (
            baseline_self
            if baseline_self is not None
            else _count_self_x([(round(x), round(y)) for x, y in base], ends, flags)
        )
        allowed_self = max(base_self, affine_self) + _SELF_X_TOL
        if perstroke_self > allowed_self:
            dsd = {}

    if dsd:
        ydev_limit = max(_DSD_MAX_YDEV_RATIO * Wg, _DSD_MAX_YDEV_FLOOR)
        max_ydev = 0.0
        for gi in dsd:
            if not (flags[gi] & _FLAG_ON_CURVE):
                continue
            dy = abs(dsd[gi][1] - base[gi][1])
            if dy > max_ydev:
                max_ydev = dy
        if max_ydev > ydev_limit:
            dsd = {}

    if dsd and s > 1.0:
        vratio = _DIAG.dsd_vstem_collapse_ratio(base, ends, flags, dsd)
        if vratio is not None and vratio < _DSD_MIN_VSTEM_WIDTH_RATIO:
            dsd = {}

    if allow_diag and claimed and not dsd and abs(s - 1.0) > 1e-6:
        claimed = set()

    def build(s_eff, lam):
        d = full_delta * lam
        out = []
        gi = 0
        for ci, cont in enumerate(conts):
            for i, (x, y) in enumerate(cont):
                if gi in claimed:
                    if gi in dsd:
                        px, py = dsd[gi]
                        if s_eff != s and s > 1e-9:
                            px = px * (s_eff / s)
                        out.append((px, py))
                    else:
                        out.append((x * s_eff, y))
                else:
                    anc = anchors[ci][i]
                    if anc is not None:
                        axb, asgn = anc
                        out.append((axb * s_eff + d * asgn + (x - axb), y))
                    else:
                        out.append((x * s_eff + d * nxs[ci][i], y))
                gi += 1
        return out

    target = mult * Wg
    lam = _solve_lambda(lambda l: _measure_coords(build(s, l), ends, flags), target)

    if s < 1.0:
        worst_base = _stems_mod().measure_worst_stem(
            {"_m": _mk_glyph(base, ends, flags)}, "_m")
        if worst_base is not None and worst_base >= 20.0:
            def _worst_at(l):
                return _stems_mod().measure_worst_stem(
                    {"_m": _mk_glyph(build(s, l), ends, flags)}, "_m")
            lam_w = _solve_lambda(_worst_at, mult * worst_base)
            if lam_w is not None and lam_w > lam:
                lam = min(lam_w, 1.10)

    coords = build(s, lam)
    used_seff = s
    if do_guard and s < 1.0:
        if baseline_self is None:
            baseline_self = _count_self_x([(round(x), round(y)) for x, y in base], ends, flags)
        scaled0 = build(s, 0.0)
        scaled0_self = _count_self_x([(round(x), round(y)) for x, y in scaled0], ends, flags)
        allowed = max(baseline_self, scaled0_self) + _SELF_X_TOL
        if _count_self_x([(round(x), round(y)) for x, y in coords], ends, flags) > allowed:
            found = None
            prev_fail = lam
            steps = 12
            for k in range(1, steps + 1):
                tl = lam * (steps - k) / steps
                tc = build(s, tl)
                if _count_self_x([(round(x), round(y)) for x, y in tc], ends, flags) <= allowed:
                    lo, hi, lo_c = tl, prev_fail, tc
                    for _ in range(6):
                        mid = (lo + hi) / 2.0
                        mc = build(s, mid)
                        if _count_self_x([(round(x), round(y)) for x, y in mc], ends, flags) <= allowed:
                            lo, lo_c = mid, mc
                        else:
                            hi = mid
                    found = lo_c
                    break
                prev_fail = tl
            if found is not None:
                coords = found
            else:
                coords = scaled0
                if _count_self_x([(round(x), round(y)) for x, y in coords], ends, flags) > allowed:
                    se = s + 0.05
                    fb = None
                    while se < 1.0 + 1e-9:
                        sc = min(se, 1.0)
                        c2 = build(sc, 0.0)
                        if _count_self_x([(round(x), round(y)) for x, y in c2], ends, flags) <= allowed:
                            fb = c2
                            used_seff = sc
                            break
                        se += 0.05
                    coords = fb if fb is not None else [(x, y) for x, y in base]
                    if fb is None:
                        used_seff = 1.0
    if allow_diag and claimed and used_seff > 1.0:
        corr = _DIAG.weld_corrections(base, ends, flags, claimed, coords)
        if corr:
            coords = [(coords[i][0] + corr.get(i, 0.0), coords[i][1]) for i in range(len(coords))]
    if used_seff > 1.0 and len(ends) >= 2:
        ocorr = _DIAG.cjk_overlap_corrections(base, ends, coords)
        if ocorr:
            coords = [(coords[i][0] + ocorr.get(i, 0.0), coords[i][1]) for i in range(len(coords))]
    if used_seff < 1.0:
        coords = _clamp_arch_spring_undercut(coords, base, ends, flags)
    elif used_seff > 1.0:
        coords = _floor_arch_spring_undercut(coords, base, ends, flags)
    return coords, ends, flags, base, used_seff


def _clamp_arch_spring_undercut(coords, base, ends, flags):
    # Inter's arch glyphs (n m r h u a...) spring off the stem with a small leftward
    # undercut at the on-curve point following the inner stem wall. The condensation
    # field moves the vertical wall (nx snapped to +-1) far more than the near-flat
    # spring point, amplifying that undercut 4-5x (n 12u->57u) into a visible notch/spur.
    # SF Pro springs flush. Clamp the condensed undercut so it never exceeds the master's,
    # translating the trailing off-curve handle rigidly to preserve the spring tangent.
    on = [bool(f & _FLAG_ON_CURVE) for f in flags]
    out = list(coords)
    st = 0
    for e in ends:
        m = e - st + 1
        if m < 3:
            st = e + 1
            continue
        for j in range(m):
            k = st + j % m
            k1 = st + (j + 1) % m
            k2 = st + (j + 2) % m
            km = st + (j - 1) % m
            if not (on[k] and on[k1] and not on[k2]):
                continue
            if abs(base[k][1] - base[k1][1]) > 6:
                continue
            base_und = base[k][0] - base[k1][0]
            if base_und <= 4:
                cond_floor = 0.0
            else:
                cond_floor = base_und
            wall_v = base[km][1] - base[k][1]
            wall_h = abs(base[k][0] - base[km][0])
            if wall_v < 60 or wall_h > 0.35 * wall_v:
                continue
            if not (base[k2][1] > base[k1][1] + 8):
                continue
            wall_x = out[k][0]
            spring_x = out[k1][0]
            und = wall_x - spring_x
            if und - cond_floor <= 1.0:
                continue
            new_spring_x = wall_x - cond_floor
            dx = new_spring_x - spring_x
            out[k1] = (new_spring_x, out[k1][1])
            out[k2] = (out[k2][0] + dx, out[k2][1])
        st = e + 1
    return out


def _floor_arch_spring_undercut(coords, base, ends, flags):
    # Inverse of the condensation clamp: under expansion the vertical wall (nx +-1) moves
    # outward far more than the near-flat spring point, so the master undercut shrinks and
    # crosses sign (n 25u->-14u, m 14u->-28u, h 31u->-6u; u springs from the bottom with
    # the opposite sign, -24u->+15u), flipping the spring to the wrong side of the wall and
    # reading as a shoulder notch. Enforce a signed minimum undercut that preserves the
    # master's side, translating the trailing off-curve handle rigidly to keep the spring
    # tangent. Sign-symmetric so top arches (n m h) and bottom arches (u) share one path.
    on = [bool(f & _FLAG_ON_CURVE) for f in flags]
    out = list(coords)
    st = 0
    for e in ends:
        m = e - st + 1
        if m < 3:
            st = e + 1
            continue
        for j in range(m):
            k = st + j % m
            k1 = st + (j + 1) % m
            k2 = st + (j + 2) % m
            km = st + (j - 1) % m
            if not (on[k] and on[k1] and not on[k2]):
                continue
            if abs(base[k][1] - base[k1][1]) > 6:
                continue
            wall_dir = base[km][1] - base[k][1]
            if abs(base[k][0] - base[km][0]) > 6 or abs(wall_dir) < 60:
                continue
            handle_dir = base[k2][1] - base[k1][1]
            if abs(handle_dir) <= 8 or (handle_dir > 0) != (wall_dir > 0):
                continue
            base_und = base[k][0] - base[k1][0]
            if abs(base_und) <= 4:
                continue
            floor = max(4.0, 0.35 * abs(base_und))
            signed_floor = math.copysign(floor, base_und)
            wall_x = out[k][0]
            spring_x = out[k1][0]
            und = wall_x - spring_x
            if base_und > 0:
                if und >= signed_floor - 1.0:
                    continue
            else:
                if und <= signed_floor + 1.0:
                    continue
            new_spring_x = wall_x - signed_floor
            dx = new_spring_x - spring_x
            out[k1] = (new_spring_x, out[k1][1])
            out[k2] = (out[k2][0] + dx, out[k2][1])
        st = e + 1
    return out


def finalize_metrics(coords, base, lsb0, rsb0, aw0, s):
    MU = _mult_mod()
    xs = [x for x, y in coords]
    xmin1 = min(xs)
    xmax1 = max(xs)
    B1 = xmax1 - xmin1
    lsb1 = MU.scale_sidebearing(lsb0, s)
    rsb1 = MU.scale_sidebearing(rsb0, s)
    translate = lsb1 - xmin1
    n = len(base)
    pt_deltas = [(round(coords[i][0] + translate) - base[i][0],
                  round(coords[i][1]) - base[i][1]) for i in range(n)]
    aw1 = round(lsb1 + B1 + rsb1)
    phantoms = [(0, 0), (aw1 - aw0, 0), (0, 0), (0, 0)]
    return pt_deltas + phantoms, aw1

