import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
import wdth_stems as ST
import wdth_multipliers as MU

BASE = sys.argv[1] if len(sys.argv) > 1 else 'build/InterludeVariable-base.ttf'

print("=== T2: multiplier curve check ===")
checks = [
    ('latin_stem(0.75)', MU.latin_stem_multiplier(0.75), 0.958),
    ('latin_stem(1.25)', MU.latin_stem_multiplier(1.25), 1.115),
    ('sb(0.75)', MU.sb_multiplier(0.75), 0.85),
    ('sb(1.25)', MU.sb_multiplier(1.25), 0.985),
    ('cjk_stem(0.75,166)', MU.cjk_stem_multiplier(0.75, 166), 0.930),
    ('cjk_stem(0.75,110)', MU.cjk_stem_multiplier(0.75, 110), 0.982),
    ('cjk_stem(0.75,77)', MU.cjk_stem_multiplier(0.75, 77), 1.012),
    ('cjk_stem(1.25,110)', MU.cjk_stem_multiplier(1.25, 110), 1.185),
]
allok = True
for name, got, want in checks:
    ok = abs(got - want) < 0.005
    allok = allok and ok
    print(f"  {'OK ' if ok else 'XX '} {name}: {got:.4f} (want {want})")
print("  T2", "PASS" if allok else "FAIL")

print("\n=== T1: stem measurement on known glyphs ===")
f = TTFont(BASE)
from fontTools.varLib.instancer import instantiateVariableFont
instantiateVariableFont(f, {'opsz': 14, 'wght': 400}, inplace=True)
glyf = f['glyf']
cmap = f.getBestCmap()
for ch, lo, hi in [('n', 160, 200), ('H', 170, 210), ('l', 150, 210),
                   ('한', 150, 185), ('永', 140, 180), ('格', 120, 165),
                   ('울', 150, 195), ('을', 150, 195), ('를', 150, 195)]:
    gn = cmap.get(ord(ch))
    wg = ST.measure_stem(glyf, gn)
    ok = wg is not None and lo <= wg <= hi
    print(f"  {'OK ' if ok else 'XX '} '{ch}' stem={wg} (expect {lo}-{hi})")

import wdth_displace as DP
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates


def apply_deltas(glyf, gn, deltas):
    g = glyf[gn]
    g.expand(glyf)
    n = len(g.coordinates)
    pts = [(g.coordinates[i][0] + deltas[i][0], g.coordinates[i][1] + deltas[i][1]) for i in range(n)]
    ng = Glyph()
    ng.numberOfContours = g.numberOfContours
    ng.coordinates = GlyphCoordinates(pts)
    ng.endPtsOfContours = list(g.endPtsOfContours)
    ng.flags = bytearray(g.flags)
    return ng


def stem_of_glyph(ng, gn_key):
    fake = {gn_key: ng}
    return ST.measure_stem(fake, gn_key)


print("\n=== T3/T4/T5: displacement v2 on subset (wdth=75) ===")
CJK = {'한', '永', '格', '門', '가'}
medians = {'cjk': 148.0, 'latin': 133.0}
for ch in ['n', 'H', 'l', 'o', '한', '永', '格', '門', '가']:
    gn = cmap.get(ord(ch))
    if not gn:
        print(f"  -- '{ch}' not in cmap")
        continue
    is_cjk = ch in CJK
    wg, rel = ST.get_stem_width(glyf, gn, is_cjk, medians)
    mult = MU.cjk_stem_multiplier(0.75, wg) if (is_cjk and rel) else MU.latin_stem_multiplier(0.75)
    res = DP.displace_v2(glyf, gn, 0.75, wg, mult)
    if res is None:
        print(f"  -- '{ch}' skipped")
        continue
    coords, ends, flags, base, seff = res
    g = glyf[gn]
    aw0, lsb0 = f['hmtx'][gn]
    bxs = [x for x, y in base]
    rsb0 = aw0 - lsb0 - (max(bxs) - min(bxs))
    deltas, aw1 = DP.finalize_metrics(coords, base, lsb0, rsb0, aw0, 0.75)
    pcount_ok = len(deltas) == len(base) + 4
    ng = apply_deltas(glyf, gn, deltas[:len(base)])
    new_stem = stem_of_glyph(ng, gn)
    target = mult * wg
    stem_ok = new_stem is not None and abs(new_stem - target) <= max(8, target * 0.08)
    gots = f"{new_stem:.0f}" if new_stem else "?"
    print(f"  '{ch}': Wg={wg:.0f} mult={mult:.3f} target={target:.0f} got={gots} "
          f"seff={seff:.2f} aw0={aw0}->aw1={aw1} pts={'OK' if pcount_ok else 'BAD'} "
          f"stem={'OK' if stem_ok else 'XX'}")

