def sb_multiplier(s):
    if s < 1.0:
        return 1.0 - 0.60 * (1.0 - s)
    return 1.0 - 0.06 * (s - 1.0)


def scale_sidebearing(sb0, s):
    if sb0 >= 0:
        return round(sb0 * sb_multiplier(s))
    return round(sb0 * s)


def latin_stem_multiplier(s):
    if s < 1.0:
        t = 1.0 - s
        return 1.0 - 0.139 * t - 0.113 * t * t
    return 1.0 + 0.460 * (s - 1.0)


W_REF_CJK = 166.0
W_FLOOR_CJK = 72.0


def cjk_thinness(Wg):
    q = (W_REF_CJK - Wg) / (W_REF_CJK - W_FLOOR_CJK)
    return max(0.0, min(1.0, q))


def cjk_perceptual_factor(s):
    factor = 1.0 + 0.1193 * (s - 1.0)
    return max(0.970, min(1.030, factor))


def cjk_stem_multiplier(s, Wg):
    m = latin_stem_multiplier(s)
    q = cjk_thinness(Wg)
    if s < 1.0:
        base = m + q * 0.09 * ((1.0 - s) / 0.25)
    else:
        base = m + q * 0.06 * ((s - 1.0) / 0.25)
    return base * cjk_perceptual_factor(s)
