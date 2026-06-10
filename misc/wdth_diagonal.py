import math

ON = 0x01


def _contours(coords, ends, flags):
    out = []
    start = 0
    for e in ends:
        pts = [(coords[k][0], coords[k][1], bool(flags[k] & ON))
               for k in range(start, e + 1)]
        out.append(pts)
        start = e + 1
    return out


def _seg_is_line(cont, i):
    n = len(cont)
    return cont[i][2] and cont[(i + 1) % n][2]


def _edge_vec(cont, i):
    n = len(cont)
    ax, ay, _ = cont[i]
    bx, by, _ = cont[(i + 1) % n]
    return bx - ax, by - ay


def _angle(dx, dy):
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    return abs(math.degrees(math.atan2(abs(dy), abs(dx))))


def _orient(cont):
    a = 0.0
    n = len(cont)
    for i in range(n):
        x1, y1, _ = cont[i]
        x2, y2, _ = cont[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return 1.0 if a > 0 else -1.0


def _outward_normal(dx, dy, ori):
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return 0.0, 0.0
    nx, ny = dy / L, -dx / L
    return nx * ori, ny * ori


def _line_intersect(p, d, q, e):
    # p + t d = q + u e
    dx, dy = d
    ex, ey = e
    den = dx * (-ey) - dy * (-ex)
    if abs(den) < 1e-9:
        return None
    qx, qy = q[0] - p[0], q[1] - p[1]
    t = (qx * (-ey) - qy * (-ex)) / den
    return p[0] + t * dx, p[1] + t * dy


def _merge_runs(cont, min_ang=15.0, max_ang=78.0, collinear_deg=4.0):
    n = len(cont)
    runs = []
    used = [False] * n
    for i in range(n):
        if used[i] or not _seg_is_line(cont, i):
            continue
        dx, dy = _edge_vec(cont, i)
        ang = _angle(dx, dy)
        if ang is None or ang < min_ang or ang > max_ang:
            continue
        idxs = [i]
        used[i] = True
        j = (i + 1) % n
        while _seg_is_line(cont, j) and not used[j]:
            d2x, d2y = _edge_vec(cont, j)
            a2 = _angle(d2x, d2y)
            if a2 is None:
                break
            cosv = (dx * d2x + dy * d2y) / (math.hypot(dx, dy) * math.hypot(d2x, d2y) + 1e-12)
            if cosv < math.cos(math.radians(collinear_deg)):
                break
            idxs.append(j)
            used[j] = True
            j = (j + 1) % n
        runs.append(idxs)
    return runs


def _feature(cont, idxs):
    n = len(cont)
    a = cont[idxs[0]]
    b = cont[(idxs[-1] + 1) % n]
    p = (a[0], a[1])
    q = (b[0], b[1])
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy)
    return {
        'idxs': idxs,
        'p': p, 'q': q,
        't': (dx / L, dy / L),
        'L': L,
        'mid': ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2),
    }


def _find_partner(feat, feats, Wg):
    tx, ty = feat['t']
    px, py = feat['p']
    best = None
    for g in feats:
        if g is feat:
            continue
        gx, gy = g['t']
        cosv = abs(tx * gx + ty * gy)
        if cosv < math.cos(math.radians(6.0)):
            continue
        nx, ny = ty, -tx
        sep = abs((g['mid'][0] - px) * nx + (g['mid'][1] - py) * ny)
        if sep < 0.45 * Wg or sep > 2.2 * Wg:
            continue
        ov = _overlap(feat, g)
        if ov < 0.30:
            continue
        if best is None or ov > best[2]:
            best = (g, sep, ov)
    return best


def _mutual_partner(feat, feats, Wg):
    p = _find_partner(feat, feats, Wg)
    if p is None:
        return None
    back = _find_partner(p[0], feats, Wg)
    if back is None or back[0] is not feat:
        return None
    return p


def _overlap(f, g):
    tx, ty = f['t']
    a0 = 0.0
    a1 = f['L']
    b0 = (g['p'][0] - f['p'][0]) * tx + (g['p'][1] - f['p'][1]) * ty
    b1 = (g['q'][0] - f['p'][0]) * tx + (g['q'][1] - f['p'][1]) * ty
    lo, hi = min(b0, b1), max(b0, b1)
    inter = max(0.0, min(a1, hi) - max(a0, lo))
    return inter / min(f['L'], g['L'] + 1e-9)


def _target_line(feat, partner, s, mult, ori):
    px, py = feat['p']
    qx, qy = feat['q']
    pA = (px * s, py)
    qA = (qx * s, qy)
    tax, tay = qA[0] - pA[0], qA[1] - pA[1]
    La = math.hypot(tax, tay)
    if La < 1e-9:
        return None
    tax, tay = tax / La, tay / La
    tx, ty = feat['t']
    T = abs((partner['p'][0] - px) * ty + (partner['p'][1] - py) * (-tx))
    T_base = T * s / math.hypot(s * tx, ty)
    T_target = mult * T
    delta = (T_target - T_base) / 2.0
    omx, omy = _outward_normal(tax, tay, ori)
    op = (pA[0] + delta * omx, pA[1] + delta * omy)
    return op, (tax, tay), delta


def _warped_line(warped, gidx_a, gidx_b):
    ax, ay = warped[gidx_a]
    bx, by = warped[gidx_b]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    return (ax, ay), (dx / L, dy / L)


def _project(pt, line):
    (ox, oy), (dx, dy) = line
    t = (pt[0] - ox) * dx + (pt[1] - oy) * dy
    return (ox + t * dx, oy + t * dy)


def _short_vstem_trunk_points(cont, min_len=180.0, tall_len=900.0, min_ang=80.0, max_gap=400.0):
    # Y has two short (610u) parallel verticals forming the trunk/foot below the arm crotch,
    # with no full-height post so _has_vstem_pair returns False and the glyph claims every
    # point for the diagonal affine. That affine, designed for the arms, shears the trunk's
    # two edges together (foot 190u->36u) and the collapse guard then rejects the whole DSD,
    # forcing an nx fallback that kinks the arms. Return the point indices of such a short
    # vertical trunk-pair so the caller can exclude them from claiming: the trunk then takes
    # the stem-preserving nx path while the arms keep their DSD. Tall posts (M N H) are left
    # to _has_vstem_pair, so this only triggers on the Y-family short trunk.
    n = len(cont)
    verts = []
    for i in range(n):
        if not _seg_is_line(cont, i):
            continue
        dx, dy = _edge_vec(cont, i)
        a = _angle(dx, dy)
        L = math.hypot(dx, dy)
        if a is not None and a > min_ang and L > min_len:
            ax, _, _ = cont[i]
            bx, _, _ = cont[(i + 1) % n]
            verts.append((i, (ax + bx) / 2.0, L))
    pts = set()
    for a in range(len(verts)):
        for b in range(a + 1, len(verts)):
            ia, xa, La = verts[a]
            ib, xb, Lb = verts[b]
            if abs(xa - xb) >= max_gap:
                continue
            if max(La, Lb) >= tall_len:
                continue
            for ei in (ia, ib):
                pts.add(ei)
                pts.add((ei + 1) % n)
    return pts


def _has_vstem_pair(cont, min_len=180.0, tall_len=900.0, min_ang=80.0, max_gap=400.0):
    # Real stem = two parallel verticals forming a bar where at least ONE member
    # is a full-height post (>= tall_len). N/M/H/K/k/b/d/p/q all have a 1118+ post.
    # A short stub pair (e.g. Y's 610/610 trunk) is NOT a stem -> treat as pure
    # diagonal so the whole glyph gets clean affine scaling (no trapezoid kink).
    n = len(cont)
    items = []
    for i in range(n):
        if not _seg_is_line(cont, i):
            continue
        dx, dy = _edge_vec(cont, i)
        a = _angle(dx, dy)
        L = math.hypot(dx, dy)
        if a is not None and a > min_ang and L > min_len:
            ax, _, _ = cont[i]
            bx, _, _ = cont[(i + 1) % n]
            items.append(((ax + bx) / 2.0, L))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if abs(items[i][0] - items[j][0]) < max_gap and max(items[i][1], items[j][1]) >= tall_len:
                return True
    return False


def claim_diagonal_points(base_coords, ends, flags, Wg, neighbor_pad=True):
    """Global point indices on mutual diagonal stroke-pairs (get pure affine, not nx-displacement)."""
    conts = _contours([(x, y) for x, y in base_coords], ends, flags)
    starts = []
    st = 0
    for e in ends:
        starts.append(st)
        st = e + 1
    claimed = set()
    for ci, cont in enumerate(conts):
        n = len(cont)
        runs = _merge_runs(cont)
        if not runs:
            continue
        feats = [_feature(cont, r) for r in runs]
        base0 = starts[ci]
        has_pair = any(_mutual_partner(f, feats, Wg) for f in feats)
        if not has_pair:
            continue
        if not _has_vstem_pair(cont):
            trunk = _short_vstem_trunk_points(cont)
            for i in range(n):
                if i in trunk:
                    continue
                claimed.add(base0 + i)
            continue
        paired_ids = set()
        for f in feats:
            if _mutual_partner(f, feats, Wg) is not None:
                paired_ids.add(id(f))
        orphan = [f for f in feats if id(f) not in paired_ids and f['L'] >= 200.0]
        stag = _staggered_pairs(orphan, Wg)
        for fa, fb in stag:
            paired_ids.add(id(fa))
            paired_ids.add(id(fb))
        stag_ids = set()
        for fa, fb in stag:
            stag_ids.add(id(fa))
            stag_ids.add(id(fb))
        pair_edges = []
        for f in feats:
            mp = _mutual_partner(f, feats, Wg)
            if mp is not None:
                pair_edges.append((0, f, mp[0]))
        remaining = [f for f in orphan if id(f) not in stag_ids]
        for o in remaining:
            if _adopt_frame(o, pair_edges, Wg) is not None:
                paired_ids.add(id(o))
        local = set()
        for f in feats:
            if id(f) not in paired_ids:
                continue
            for ei in f['idxs']:
                local.add(ei)
                local.add((ei + 1) % n)
        for i in range(n):
            if i in local:
                claimed.add(base0 + i)
                continue
            if not (flags[base0 + i] & ON):
                if (i - 1) % n in local and (i + 1) % n in local:
                    claimed.add(base0 + i)
    return claimed


EXP_ANGLE_K = 0.45
EXP_ANGLE_MIN = 0.88


def _stroke_affine(u, s, m):
    ux, uy = u
    Hux, Huy = s * ux, uy
    vlen = math.hypot(Hux, Huy)
    if vlen < 1e-9:
        return None
    # Expansion (s>1) rotates diagonals toward horizontal; perpendicular thickness
    # is preserved by the affine but a more-horizontal stroke reads optically heavier
    # (K leg 47deg->33deg at wd150 looks bottom-heavy). SF Pro keeps diagonals
    # visually even by thinning them as they flatten. Reduce perpendicular thickness
    # by the angle change, blended (k) and clamped (min) so Thin diagonals don't get
    # brittle. Per-stroke so K's leg and arm get angle-correct independent weights.
    if s > 1.0 and abs(uy) > 1e-9:
        sin0 = abs(uy)
        sin1 = abs(uy) / vlen
        keep = sin1 / sin0
        comp = 1.0 - EXP_ANGLE_K * max(0.0, 1.0 - keep)
        m = m * max(EXP_ANGLE_MIN, min(1.0, comp))
    npx, npy = -Huy / vlen, Hux / vlen
    nx, ny = -uy, ux
    a00 = Hux * ux + m * npx * nx
    a01 = Hux * uy + m * npx * ny
    a10 = Huy * ux + m * npy * nx
    a11 = Huy * uy + m * npy * ny
    return (a00, a01, a10, a11)


def _apply_affine(A, c0, p):
    a00, a01, a10, a11 = A
    dx, dy = p[0] - c0[0], p[1] - c0[1]
    return (a00 * dx + a01 * dy, a10 * dx + a11 * dy)


def _transform_point(A, c0, Hc0, p):
    rel = _apply_affine(A, c0, p)
    return Hc0[0] + rel[0], Hc0[1] + rel[1]


def _line_from_points(p, q):
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    return p, (dx / L, dy / L)


def _interval_gap(base, other):
    tx, ty = base['t']
    b0 = (other['p'][0] - base['p'][0]) * tx + (other['p'][1] - base['p'][1]) * ty
    b1 = (other['q'][0] - base['p'][0]) * tx + (other['q'][1] - base['p'][1]) * ty
    lo, hi = min(b0, b1), max(b0, b1)
    if hi < 0.0:
        return -hi
    if lo > base['L']:
        return lo - base['L']
    return 0.0


def _staggered_score(f, g, Wg):
    tx, ty = f['t']
    gx, gy = g['t']
    if abs(tx * gx + ty * gy) < math.cos(math.radians(6.0)):
        return None
    nx, ny = ty, -tx
    sep = abs((g['mid'][0] - f['p'][0]) * nx + (g['mid'][1] - f['p'][1]) * ny)
    if sep < 0.45 * Wg or sep > 2.2 * Wg:
        return None
    if _overlap(f, g) >= 0.30:
        return None
    gap = _interval_gap(f, g)
    if gap > max(2.0 * Wg, 0.35 * min(f['L'], g['L'])):
        return None
    mx, my = g['mid'][0] - f['mid'][0], g['mid'][1] - f['mid'][1]
    ml = math.hypot(mx, my)
    if ml < 1e-9:
        return None
    if abs((mx / ml) * tx + (my / ml) * ty) < math.cos(math.radians(20.0)):
        return None
    return (gap, abs(sep - Wg), -min(f['L'], g['L']))


def _staggered_partner(feat, orphans, Wg):
    best = None
    for g in orphans:
        if g is feat:
            continue
        sc = _staggered_score(feat, g, Wg)
        if sc is None:
            continue
        if best is None or sc < best[1]:
            best = (g, sc)
    return best[0] if best else None


def _staggered_pairs(orphans, Wg):
    pairs = []
    seen = set()
    for f in orphans:
        if id(f) in seen:
            continue
        p = _staggered_partner(f, orphans, Wg)
        if p is None or id(p) in seen:
            continue
        if _staggered_partner(p, orphans, Wg) is not f:
            continue
        seen.add(id(f))
        seen.add(id(p))
        pairs.append((f, p))
    return pairs


def _adopt_frame(orphan, pair_edges, Wg):
    ox, oy = orphan['t']
    best = None
    for fidx, fa, fb in pair_edges:
        for edge in (fa, fb):
            ex, ey = edge['t']
            if abs(ox * ex + oy * ey) < math.cos(math.radians(6.0)):
                continue
            nx, ny = ey, -ex
            pd = abs((orphan['mid'][0] - edge['p'][0]) * nx + (orphan['mid'][1] - edge['p'][1]) * ny)
            if pd > max(12.0, 0.30 * Wg):
                continue
            gap = _interval_gap(edge, orphan)
            if gap > max(2.0 * Wg, 0.35 * min(orphan['L'], edge['L'])):
                continue
            if best is None or pd < best[1]:
                best = (fidx, pd)
    return best[0] if best else None


def _stroke_pairs(cont, feats, Wg):
    seen = set()
    pairs = []
    for fi, f in enumerate(feats):
        mp = _mutual_partner(f, feats, Wg)
        if mp is None:
            continue
        pj = feats.index(mp[0])
        key = (min(fi, pj), max(fi, pj))
        if key in seen:
            continue
        seen.add(key)
        pairs.append((f, mp[0]))
    return pairs


def _pair_centerline(fa, fb):
    tax, tay = fa['t']
    tbx, tby = fb['t']
    if tax * tbx + tay * tby < 0:
        tbx, tby = -tbx, -tby
    ux, uy = (tax + tbx) / 2.0, (tay + tby) / 2.0
    L = math.hypot(ux, uy)
    if L < 1e-9:
        return None
    ux, uy = ux / L, uy / L
    c0 = ((fa['mid'][0] + fb['mid'][0]) / 2.0, (fa['mid'][1] + fb['mid'][1]) / 2.0)
    return (ux, uy), c0


def diagonal_stroke_deltas(base_coords, ends, flags, Wg, s, m):
    """Per-stroke affine for pure-diagonal glyphs; returns {global_idx: (x, y)}.

    Each stroke pair gets one affine so its edges stay straight while perpendicular
    thickness is restored to m*original (plain x*s thins it by an angle-dependent
    factor). Shared join points land on the intersection of the transformed edges.
    """
    conts = _contours([(x, y) for x, y in base_coords], ends, flags)
    starts = []
    st = 0
    for e in ends:
        starts.append(st)
        st = e + 1
    new_pos = {}
    multi = {}
    for ci, cont in enumerate(conts):
        n = len(cont)
        base0 = starts[ci]
        runs = _merge_runs(cont)
        if not runs:
            continue
        feats = [_feature(cont, r) for r in runs]
        trunk_pts = _short_vstem_trunk_points(cont) if not _has_vstem_pair(cont) else set()
        pairs = _stroke_pairs(cont, feats, Wg)
        paired = set(id(f) for p in pairs for f in p)
        orphan = [f for f in feats if id(f) not in paired and f['L'] >= 200.0]
        if orphan:
            recovered = _staggered_pairs(orphan, Wg)
            if recovered:
                pairs = pairs + recovered
                paired = set(id(f) for p in pairs for f in p)
                orphan = [f for f in feats if id(f) not in paired and f['L'] >= 200.0]
        frames = []
        assigned = set()
        owner_frame = {}
        pair_edges = []
        for fa, fb in pairs:
            cl = _pair_centerline(fa, fb)
            if cl is None:
                continue
            u, c0 = cl
            A = _stroke_affine(u, s, m)
            if A is None:
                continue
            Hc0 = (s * c0[0], c0[1])
            fidx = len(frames)
            frames.append((u, c0, A, Hc0))
            pair_edges.append((fidx, fa, fb))
            for feat in (fa, fb):
                ep = _transform_point(A, c0, Hc0, feat['p'])
                eq = _transform_point(A, c0, Hc0, feat['q'])
                edge_line = _line_from_points(ep, eq)
                if edge_line is None:
                    continue
                pts = set()
                for ei in feat['idxs']:
                    pts.add(ei)
                    pts.add((ei + 1) % n)
                for i in pts:
                    gi = base0 + i
                    assigned.add(i)
                    owner_frame[i] = fidx
                    pos = _transform_point(A, c0, Hc0, cont[i])
                    multi.setdefault(gi, []).append((pos, edge_line))
        if orphan:
            for o in orphan:
                fidx = _adopt_frame(o, pair_edges, Wg)
                if fidx is None:
                    return {}
                u, c0, A, Hc0 = frames[fidx]
                for ei in o['idxs']:
                    for i in (ei, (ei + 1) % n):
                        if i in assigned:
                            continue
                        assigned.add(i)
                        owner_frame[i] = fidx
                        pos = _transform_point(A, c0, Hc0, cont[i])
                        multi.setdefault(base0 + i, []).append(
                            (pos, (pos, (s * u[0], u[1]))))
        if frames:
            for i in range(n):
                if i in assigned:
                    continue
                if i in trunk_pts:
                    continue
                best = None
                for j, fj in owner_frame.items():
                    rd = min((i - j) % n, (j - i) % n)
                    if best is None or rd < best[0]:
                        best = (rd, fj)
                if best is None:
                    continue
                u, c0, A, Hc0 = frames[best[1]]
                pos = _transform_point(A, c0, Hc0, cont[i])
                multi.setdefault(base0 + i, []).append((pos, (pos, (s * u[0], u[1]))))
    for gi, cands in multi.items():
        if len(cands) == 1:
            new_pos[gi] = cands[0][0]
        else:
            pt = _resolve_join([c[1] for c in cands], [c[0] for c in cands], Wg)
            if pt is None:
                ps = [c[0] for c in cands]
                pt = (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))
            new_pos[gi] = pt
    _flatten_terminals(conts, starts, flags, multi, new_pos)
    return new_pos


def _flatten_terminals(conts, starts, flags, multi, new_pos):
    # Diagonal terminal caps are horizontal flat cuts in the master, but the per-stroke
    # affine maps a horizontal vector (dx,0) to (a00*dx, a10*dx) with a10!=0, tilting
    # the cap (K/A/X terminals went 0deg->11deg at wd75). Restore flatness by placing
    # each cap endpoint on the intersection of its affine-transformed body edge_line and
    # the preserved master-Y horizontal line. Keeps body edges straight AND cap flat.
    ally = [y for cont in conts for (x, y, on) in cont]
    if not ally:
        return
    ymin, ymax = min(ally), max(ally)
    for ci, cont in enumerate(conts):
        n = len(cont)
        base0 = starts[ci]
        for i in range(n):
            a = cont[i]
            j = (i + 1) % n
            b = cont[j]
            if not (a[2] and b[2]):
                continue
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            L = math.hypot(dx, dy)
            if L < 100.0 or L > 260.0:
                continue
            if abs(dy) > 0.18 * abs(dx):
                continue
            ymid = (a[1] + b[1]) / 2.0
            if not (ymid < ymin + 120 or ymid > ymax - 120):
                continue
            gi_a = base0 + i
            gi_b = base0 + j
            la = _body_edge_for(multi, gi_a)
            lb = _body_edge_for(multi, gi_b)
            if la is None or lb is None or gi_a not in new_pos or gi_b not in new_pos:
                continue
            ya = a[1]
            yb = b[1]
            pa = _intersect_horizontal(la, ya)
            pb = _intersect_horizontal(lb, yb)
            if pa is not None:
                new_pos[gi_a] = pa
            if pb is not None:
                new_pos[gi_b] = pb


def _body_edge_for(multi, gi):
    cands = multi.get(gi)
    if not cands:
        return None
    for pos, line in cands:
        o, d = line
        if abs(d[1]) > 0.18 * abs(d[0]):
            return line
    return None


def _intersect_horizontal(line, y):
    (ox, oy), (dx, dy) = line
    if abs(dy) < 1e-9:
        return None
    t = (y - oy) / dy
    return (ox + t * dx, y)


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _resolve_join(lines, fallback_positions, Wg=None):
    cx = sum(p[0] for p in fallback_positions) / len(fallback_positions)
    cy = sum(p[1] for p in fallback_positions) / len(fallback_positions)
    spread = max(math.hypot(p[0] - cx, p[1] - cy) for p in fallback_positions)
    max_dist = max(24.0, 8.0 * spread, 1.25 * Wg) if Wg is not None else max(24.0, 8.0 * spread)
    best = None
    for i in range(len(lines)):
        o1, d1 = lines[i]
        for j in range(i + 1, len(lines)):
            o2, d2 = lines[j]
            if abs(_cross(d1, d2)) < math.sin(math.radians(6.0)):
                continue
            pt = _line_intersect(o1, d1, o2, d2)
            if pt is None:
                continue
            dist = math.hypot(pt[0] - cx, pt[1] - cy)
            if best is None or dist < best[0]:
                best = (dist, pt)
    if best is not None and best[0] <= max_dist:
        return best[1]
    return None


def cjk_overlap_corrections(base_coords, ends, disp_coords, overlap_min=18.0):
    # CJK jamo are built from separate overlapping contours (vertical stem + horizontal
    # branch). On expansion the normal-offset term (d*nx) pushes the branch's inner
    # edge and the stem edge apart, destroying the overlap that made them look joined
    # (ㅏ: 26u overlap -> 5u gap at wd125). Re-establish the master overlap by moving
    # ONLY the branch's inner terminal edge back into the stem; that extension is hidden
    # inside the stem fill so it is kink-free. Right-attaching (ㅏㅐㅑ) and left (ㅓ).
    base = [(x, y) for x, y in base_coords]
    disp = [(x, y) for x, y in disp_coords]
    starts = []
    st = 0
    for e in ends:
        starts.append(st)
        st = e + 1

    def boxes(coords):
        bs = []
        for ci in range(len(ends)):
            a = starts[ci]
            b = ends[ci]
            xs = [coords[i][0] for i in range(a, b + 1)]
            ys = [coords[i][1] for i in range(a, b + 1)]
            bs.append((min(xs), max(xs), min(ys), max(ys), a, b))
        return bs

    bb = boxes(base)
    db = boxes(disp)
    corr = {}
    for hi, (hx0, hx1, hy0, hy1, ha, hb) in enumerate(bb):
        if (hx1 - hx0) <= (hy1 - hy0):
            continue
        for vi, (vx0, vx1, vy0, vy1, va, vb) in enumerate(bb):
            if vi == hi or (vx1 - vx0) >= (vy1 - vy0):
                continue
            if not (vy0 <= hy0 and hy1 <= vy1):
                continue
            if vx0 <= hx0 <= vx1 and (vx1 - hx0) >= overlap_min:
                req = vx1 - hx0
                d_over = db[vi][1] - db[hi][0]
                if d_over < req:
                    shift = -(req - d_over)
                    for i in range(ha, hb + 1):
                        if abs(base[i][0] - hx0) <= 2:
                            corr[i] = corr.get(i, 0.0) + shift
            if vx0 <= hx1 <= vx1 and (hx1 - vx0) >= overlap_min:
                req = hx1 - vx0
                d_over = db[hi][1] - db[vi][0]
                if d_over < req:
                    shift = req - d_over
                    for i in range(ha, hb + 1):
                        if abs(base[i][0] - hx1) <= 2:
                            corr[i] = corr.get(i, 0.0) + shift
    return corr


def weld_corrections(base_coords, ends, flags, claimed, disp_coords, overlap_min=8.0, pad=40.0):
    base = [(x, y) for x, y in base_coords]
    disp = [(x, y) for x, y in disp_coords]
    starts = []
    st = 0
    for e in ends:
        starts.append(st)
        st = e + 1
    conts = _contours(base, ends, flags)
    corr = {}
    for ci, cont in enumerate(conts):
        base0 = starts[ci]
        end0 = ends[ci]
        stem_idxs = list(range(base0, end0 + 1))
        if any(i in claimed for i in stem_idxs):
            continue
        if not _has_vstem_pair(cont):
            continue
        sxs = [base[i][0] for i in stem_idxs]
        sys_ = [base[i][1] for i in stem_idxs]
        L0, R0 = min(sxs), max(sxs)
        ylo, yhi = min(sys_), max(sys_)
        cx = (L0 + R0) / 2.0
        right_root = None
        left_root = None
        for gi in claimed:
            if base0 <= gi <= end0:
                continue
            bx, by = base[gi]
            if by < ylo - 2 or by > yhi + 2:
                continue
            if bx < L0 - pad or bx > R0 + pad:
                continue
            if bx >= cx:
                if bx <= R0 and (right_root is None or bx > base[right_root][0]):
                    right_root = gi
            else:
                if bx >= L0 and (left_root is None or bx < base[left_root][0]):
                    left_root = gi
        if right_root is not None:
            R_thin = max(disp[i][0] for i in stem_idxs)
            overlap_req = max(overlap_min, R0 - base[right_root][0])
            R_req = disp[right_root][0] + overlap_req
            shift = R_req - R_thin
            if shift > 0:
                for i in stem_idxs:
                    corr[i] = corr.get(i, 0.0) + shift
        if left_root is not None:
            L_thin = min(disp[i][0] for i in stem_idxs)
            overlap_req = max(overlap_min, base[left_root][0] - L0)
            L_req = disp[left_root][0] - overlap_req
            shift = L_req - L_thin
            if shift < 0:
                for i in stem_idxs:
                    corr[i] = corr.get(i, 0.0) + shift
    return corr


def dsd_vstem_collapse_ratio(base_coords, ends, flags, dsd):
    # dsd (per-stroke diagonal affine) only models the diagonal strokes; a glyph's shared
    # vertical trunk (e.g. the stem below Y's arms) is unassigned and inherits a diagonal
    # arm's affine via the nearest-frame fallback, which shears its two edges together.
    # For Y this collapses the foot from 190u to 36u (-> crossed after wght interp). Detect
    # near-vertical tall stem pairs and return the minimum signed dsd/base width ratio over
    # samples along the overlap; the caller rejects dsd when this drops too low. Signed (not
    # abs) so an inverted bowtie reads as negative and is unconditionally caught.
    if not dsd:
        return None
    base = [(x, y) for x, y in base_coords]
    n = len(base)
    on = [bool(f & ON) for f in flags]
    segs = []
    st = 0
    for e in ends:
        cont = list(range(st, e + 1))
        st = e + 1
        nc = len(cont)
        for k in range(nc):
            i = cont[k]
            j = cont[(k + 1) % nc]
            if not (on[i] and on[j]):
                continue
            dx = base[j][0] - base[i][0]
            dy = base[j][1] - base[i][1]
            if abs(dy) < 200:
                continue
            if abs(math.degrees(math.atan2(abs(dy), abs(dx)))) < 75:
                continue
            segs.append((i, j))

    def dpos(idx):
        return dsd[idx] if idx in dsd else (base[idx][0], base[idx][1])

    worst = None
    for a in range(len(segs)):
        for b in range(a + 1, len(segs)):
            i1, j1 = segs[a]
            i2, j2 = segs[b]
            ylo1, yhi1 = sorted((base[i1][1], base[j1][1]))
            ylo2, yhi2 = sorted((base[i2][1], base[j2][1]))
            ov_lo = max(ylo1, ylo2)
            ov_hi = min(yhi1, yhi2)
            if ov_hi - ov_lo < 150:
                continue
            cx1 = (base[i1][0] + base[j1][0]) / 2.0
            cx2 = (base[i2][0] + base[j2][0]) / 2.0
            base_gap = abs(cx1 - cx2)
            if base_gap < 40 or base_gap > 400:
                continue
            if cx1 <= cx2:
                (lo1, lo2), (hi1, hi2) = (i1, j1), (i2, j2)
                lseg = (i1, j1)
                rseg = (i2, j2)
            else:
                lseg = (i2, j2)
                rseg = (i1, j1)

            def edge_x(seg, y, coords):
                p, q = seg
                (x0, y0), (x1, y1) = coords[p], coords[q]
                if abs(y1 - y0) < 1e-6:
                    return (x0 + x1) / 2.0
                t = (y - y0) / (y1 - y0)
                return x0 + t * (x1 - x0)

            base_pts = base
            disp_pts = [dpos(k) for k in range(n)]
            for f in (0.0, 0.25, 0.5, 0.75, 1.0):
                y = ov_lo + f * (ov_hi - ov_lo)
                bw = edge_x(rseg, y, base_pts) - edge_x(lseg, y, base_pts)
                dw = edge_x(rseg, y, disp_pts) - edge_x(lseg, y, disp_pts)
                if bw <= 1e-6:
                    continue
                ratio = dw / bw
                if worst is None or ratio < worst:
                    worst = ratio
    return worst


def e_overlap_wall_pull(coords, ends, flags, shift=-13.0, handle_taper=0.7):
    # Width expansion separates the e crossbar tip from the bowl inner wall, shrinking
    # the eye overlap (13u at thin-exp reads as a notch). Moving the tip makes a spur;
    # instead pull the wall + its handle leftward to the fixed tongue. Tip = on-curve
    # point ending a long rightward flat edge whose next on-curve point sits left-down.
    # Gating to thin x expand is done by the caller's TupleVariation axes; here we emit
    # the empirically-validated fixed shift (overlap 13->26u, kink/spur-free).
    n = len(coords)
    on = [bool(f & 1) for f in flags]
    xs = [c[0] for c in coords]
    W = max(xs) - min(xs)
    if W <= 0:
        return {}
    tip = None
    for i in range(n):
        if not on[i]:
            continue
        pj = (i - 1) % n
        x0, y0 = coords[pj]
        x1, y1 = coords[i]
        if abs(y1 - y0) > 3:
            continue
        if (x1 - x0) < 0.30 * W:
            continue
        nj = (i + 1) % n
        x2, y2 = coords[nj]
        if not (x2 < x1 and y2 < y1):
            continue
        if tip is not None:
            return {}
        tip = i
    if tip is None:
        return {}
    wall = (tip + 1) % n
    corr = {wall: (shift, 0.0)}
    handle = (wall + 1) % n
    if not on[handle]:
        corr[handle] = (shift * handle_taper, 0.0)
    return corr








