# Arch-stem G2 fairing for the wdth axis.
#
# Problem: where a bowl/arch (a, b, d, g, p, q ...) departs a vertical stem, the
# condensed master amplifies a pre-existing curvature discontinuity at the
# arch->wall junction, producing a visible "ramp reversal" (the curvature climbs
# then dips then climbs again instead of decaying monotonically into the wall).
#
# Fix: treat the run of off-curve controls between the two on-curve endpoints
# (A = arch crest side, B = wall landing) as a unit. Map the *master* control
# polygon onto the condensed endpoint frame with a similarity transform (this
# preserves the master's curvature ratios exactly), then distribute the residual
# wall-alignment error with an index-linear ramp so the last control lands on the
# wall. Curvature ratios are inherited from the (good) master; only the global
# placement is re-derived. Gated: applied only when condensation actually made the
# ramp worse than the master, so well-behaved arches are left untouched.
import math

WALL_MIN = 60.0     # min collinear wall length (units) to qualify as a stem
WALL_DOT = 0.985    # cos tolerance for "still the same straight wall"
MAX_OFF = 5         # max off-curve controls in one arch run
_FLAG_ON = 0x01


def _contours(ends):
    out = []
    start = 0
    for e in ends:
        out.append(list(range(start, e + 1)))
        start = e + 1
    return out


def _wall_run(co, idxs, i1):
    """Collinear wall length leaving on-curve point idxs[i1]. Follows the
    straight run through off-curve points too (a wall can pass through an
    off-curve control as long as direction holds)."""
    m = len(idxs)
    B = idxs[i1]
    nxt = idxs[(i1 + 1) % m]
    d0 = (co[nxt][0] - co[B][0], co[nxt][1] - co[B][1])
    L0 = math.hypot(*d0)
    if L0 < 1e-6:
        return 0.0, False
    u0 = (d0[0] / L0, d0[1] / L0)
    total = 0.0
    prev = co[B]
    k = (i1 + 1) % m
    steps = 0
    while steps < m:
        cur = co[idxs[k]]
        d = (cur[0] - prev[0], cur[1] - prev[1])
        L = math.hypot(*d)
        if L < 1e-6:
            break
        if (d[0] * u0[0] + d[1] * u0[1]) / L < WALL_DOT:
            break
        total += L
        prev = cur
        k = (k + 1) % m
        steps += 1
        if k == i1:
            break
    vert = abs(u0[0]) < abs(u0[1])
    return total, vert


def find_arch_runs(co, flags, ends):
    """Locate arch->wall runs. Returns (A, [off-curve idxs], B, wall_next idx)."""
    runs = []
    for idxs in _contours(ends):
        m = len(idxs)
        ons = [k for k in range(m) if flags[idxs[k]] & _FLAG_ON]
        if len(ons) < 2:
            continue
        for a in range(len(ons)):
            i0 = ons[a]
            i1 = ons[(a + 1) % len(ons)]
            seq = []
            k = (i0 + 1) % m
            while k != i1 and len(seq) <= MAX_OFF:
                seq.append(idxs[k])
                k = (k + 1) % m
            if not (1 <= len(seq) <= MAX_OFF):
                continue
            if any(flags[g] & _FLAG_ON for g in seq):
                continue
            wlen, vert = _wall_run(co, idxs, i1)
            if wlen >= WALL_MIN and vert:
                runs.append((idxs[i0], list(seq), idxs[i1], idxs[(i1 + 1) % m]))
    return runs


def _qcurv(p0, c, p1, t):
    d1 = (2 * (1 - t) * (c[0] - p0[0]) + 2 * t * (p1[0] - c[0]),
          2 * (1 - t) * (c[1] - p0[1]) + 2 * t * (p1[1] - c[1]))
    d2 = (2 * (p1[0] - 2 * c[0] + p0[0]), 2 * (p1[1] - 2 * c[1] + p0[1]))
    den = (d1[0] ** 2 + d1[1] ** 2) ** 1.5
    return (d1[0] * d2[1] - d1[1] * d2[0]) / den if den > 1e-9 else 0.0


def _ramp_rev(A, seq, B, co):
    pts = [co[A]] + [co[i] for i in seq] + [co[B]]
    segs = []
    prev = pts[0]
    for k in range(1, len(pts) - 1):
        c = pts[k]
        nx = pts[k + 1]
        end = nx if k == len(pts) - 2 else ((c[0] + nx[0]) / 2, (c[1] + nx[1]) / 2)
        segs.append((prev, c, end))
        prev = end
    ks = []
    for a, c, b in segs:
        for t in range(9):
            ks.append(_qcurv(a, c, b, t / 8.0))
    return sum(1 for i in range(2, len(ks))
               if (ks[i] - ks[i - 1]) * (ks[i - 1] - ks[i - 2]) < -1e-9)


def _similarity(Am, Bm, Ac, Bc):
    dm = (Bm[0] - Am[0], Bm[1] - Am[1])
    dm2 = dm[0] ** 2 + dm[1] ** 2
    if dm2 < 1e-9:
        return None
    dc = (Bc[0] - Ac[0], Bc[1] - Ac[1])
    a = (dc[0] * dm[0] + dc[1] * dm[1]) / dm2
    b = (dc[1] * dm[0] - dc[0] * dm[1]) / dm2

    def T(p):
        v = (p[0] - Am[0], p[1] - Am[1])
        return (Ac[0] + a * v[0] - b * v[1], Ac[1] + b * v[0] + a * v[1])
    return T


def _condensed(coords, out):
    cc = list(coords)
    for ref, (dx, dy) in out.items():
        cc[ref] = (coords[ref][0] + dx, coords[ref][1] + dy)
    return cc


def fair_arches(coords, ends, flags, out, s):
    if s >= 1.0:
        return
    co_c = _condensed(coords, out)
    runs_m = find_arch_runs(coords, flags, ends)
    runs_c = find_arch_runs(co_c, flags, ends)
    by_a = {A: (seq, B, nxt) for A, seq, B, nxt in runs_m}
    for A, seq, B, nxt in runs_c:
        if A not in by_a:
            continue
        mseq, mB, _ = by_a[A]
        if _ramp_rev(A, seq, B, co_c) <= _ramp_rev(A, mseq, mB, coords):
            continue
        T = _similarity(coords[A], coords[B], co_c[A], co_c[B])
        if T is None:
            continue
        sim = [T(coords[i]) for i in seq]
        wd = (co_c[nxt][0] - co_c[B][0], co_c[nxt][1] - co_c[B][1])
        vert = abs(wd[0]) < abs(wd[1])
        axis = co_c[B][0] if vert else co_c[B][1]
        n = len(seq)
        err = (axis - sim[-1][0]) if vert else (axis - sim[-1][1])
        for k in range(n):
            frac = (k + 1) / n
            px, py = sim[k]
            if vert:
                px += frac * err
            else:
                py += frac * err
            if k == n - 1:
                if vert:
                    px = axis
                else:
                    py = axis
            ref = seq[k]
            out[ref] = (px - coords[ref][0], py - coords[ref][1])
