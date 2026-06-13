def sb_multiplier(s):
    if s < 1.0:
        return 1.0 - 0.60 * (1.0 - s)
    return 1.0 - 0.06 * (s - 1.0)



def scale_sidebearing(sb0, s):
    if sb0 >= 0:
        return round(sb0 * sb_multiplier(s))
    return round(sb0 * s)


# SF Pro's wdth axis scales STROKE WEIGHT with width: its vertical stems measure
# 0.957x at wd75 and 1.116x at wd125 of the wd100 master (l/I/H/n/o/c/e all move
# together, ~identical ratios, which is why SF Pro reads uniform at every width).
# Interlude previously froze the latin stem at 1.0, so straight stems stayed put
# while the displacement field still nudged curves a few percent -> straight and
# round glyphs drifted out of weight sync (the "lumpy" inconsistency). Matching
# SF Pro's slope makes every stroke scale by the same factor. Slopes differ per
# side (condense vs expand) because SF Pro's progression is asymmetric.
LATIN_STEM_COND_SLOPE = 0.172  # 1 - 0.172*(1-s): s=0.75 -> 0.957
LATIN_STEM_EXP_SLOPE = 0.464   # 1 + 0.464*(s-1): s=1.25 -> 1.116


def latin_stem_multiplier(s):
    if s < 1.0:
        return 1.0 - LATIN_STEM_COND_SLOPE * (1.0 - s)
    return 1.0 + LATIN_STEM_EXP_SLOPE * (s - 1.0)


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
