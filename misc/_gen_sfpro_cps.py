"""Regenerate misc/wdth_sfpro_cps.py from the system SF Pro variable font.

Extracts every cmap codepoint whose glyph carries a nonzero gvar delta on the
wdth axis (i.e. SF Pro actually condenses/expands it). Run when SF Pro updates:

    python3 misc/_gen_sfpro_cps.py

Requires /Library/Fonts/SF-Pro.ttf (ships with macOS SF font download).
"""
import os
from fontTools.ttLib import TTFont

SRC = '/Library/Fonts/SF-Pro.ttf'
OUT = os.path.join(os.path.dirname(__file__), 'wdth_sfpro_cps.py')


def main():
    f = TTFont(SRC)
    gvar = f['gvar']
    cmap = f.getBestCmap()
    varies = set()
    for cp, gn in cmap.items():
        for tv in gvar.variations.get(gn, []):
            if 'wdth' in tv.axes and any(c and (c[0] or c[1]) for c in tv.coordinates if c):
                varies.add(cp)
                break
    cps = sorted(varies)
    ranges = []
    start = prev = cps[0]
    for cp in cps[1:]:
        if cp == prev + 1:
            prev = cp
        else:
            ranges.append((start, prev))
            start = prev = cp
    ranges.append((start, prev))

    with open(OUT, 'w') as fp:
        fp.write('"""Codepoints that SF Pro varies on its wdth axis (extracted from\n')
        fp.write('/Library/Fonts/SF-Pro.ttf: glyphs with nonzero wdth gvar deltas).\n')
        fp.write('Used as the latin/symbol whitelist for which glyphs Interlude width-varies,\n')
        fp.write('matching Apple\'s decision to leave arrows/pictographs fixed while varying\n')
        fp.write('letters, digits, common punctuation, currency and a few math symbols.\n')
        fp.write('Regenerate with misc/_gen_sfpro_cps.py if SF Pro changes.\n"""\n\n')
        fp.write('SFPRO_WDTH_RANGES = (\n')
        for a, b in ranges:
            fp.write(f'    (0x{a:04X}, 0x{b:04X}),\n')
        fp.write(')\n\n\n')
        fp.write('def sfpro_varies(cp):\n')
        fp.write('    if cp is None:\n        return False\n')
        fp.write('    for a, b in SFPRO_WDTH_RANGES:\n        if a <= cp <= b:\n            return True\n')
        fp.write('    return False\n\n\n')
        fp.write('# Flattened set for O(1) membership (used in the per-glyph hot loop).\n')
        fp.write('SFPRO_WDTH_CPS = frozenset(\n')
        fp.write('    cp for a, b in SFPRO_WDTH_RANGES for cp in range(a, b + 1)\n')
        fp.write(')\n')
    print(f'{len(cps)} codepoints -> {len(ranges)} ranges -> {OUT}')


if __name__ == '__main__':
    main()
