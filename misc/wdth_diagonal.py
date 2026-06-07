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
            for i in range(n):
                claimed.add(base0 + i)
            continue
        local = set()
        for f in feats:
            if _mutual_partner(f, feats, Wg) is None:
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




