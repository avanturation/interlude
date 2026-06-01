"""Generate dynamic subset woff2 files and CSS from a variable TTF.

Uses Pretendard JP's unicode-range split as reference, then subsets
the Inter CJK variable font into matching chunks.
"""
import sys
import os
import re
from multiprocessing import Pool, cpu_count
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options


def parse_unicode_ranges(css_path):
    with open(css_path) as f:
        content = f.read()
    return re.findall(r'unicode-range:\s*([^;]+);', content)


def unicode_range_to_codepoints(range_str):
    codepoints = set()
    for part in range_str.split(','):
        part = part.strip().replace('U+', '').replace('u+', '')
        if '?' in part:
            prefix = part.replace('?', '')
            suffix_len = part.count('?')
            start = int(prefix + '0' * suffix_len, 16)
            end = int(prefix + 'F' * suffix_len, 16)
            codepoints.update(range(start, end + 1))
        elif '-' in part:
            start, end = part.split('-')
            codepoints.update(range(int(start, 16), int(end, 16) + 1))
        else:
            codepoints.add(int(part, 16))
    return codepoints


# Codepoints that must never be split across subset files. GSUB ligature
# substitution (calt/dlig/rlig: -> => <= |> fi fl ...) only works when every
# input glyph lives in the SAME woff2. Pretendard's CJK-oriented unicode-range
# split scatters these ASCII operators across files, which silently breaks all
# multi-character ligatures. Keeping the full ASCII block + arrows together in a
# single "base" subset fixes the whole ligature system at once (and these are
# the highest-frequency glyphs, so co-locating them helps load performance too).
BASE_CODEPOINTS = set(range(0x0020, 0x007F)) | set(range(0x2190, 0x2200))


def codepoints_to_range_str(codepoints):
    """Compact a set of codepoints into a CSS unicode-range string."""
    cps = sorted(codepoints)
    parts = []
    start = prev = cps[0]
    for cp in cps[1:]:
        if cp == prev + 1:
            prev = cp
            continue
        parts.append((start, prev))
        start = prev = cp
    parts.append((start, prev))
    out = []
    for a, b in parts:
        out.append(f"U+{a:04X}" if a == b else f"U+{a:04X}-{b:04X}")
    return ", ".join(out)


def _subset_one(args):
    font_path, codepoints, output_path = args
    try:
        font = TTFont(font_path)
        options = Options()
        options.flavor = 'woff2'
        options.layout_features = ['*']
        options.glyph_names = False
        options.name_IDs = [0, 1, 2, 3, 4, 5, 6]
        options.drop_tables = ['DSIG', 'MVAR']

        subsetter = Subsetter(options=options)
        subsetter.populate(unicodes=codepoints)
        subsetter.subset(font)
        font.flavor = 'woff2'
        font.save(output_path)

        size_kb = os.path.getsize(output_path) / 1024
        if size_kb < 0.1:
            os.remove(output_path)
            return None
        return output_path
    except Exception:
        return None


def generate(font_path, reference_css, output_dir, family_name, css_filename):
    os.makedirs(output_dir, exist_ok=True)

    ranges = parse_unicode_ranges(reference_css)
    font_basename = os.path.splitext(os.path.basename(font_path))[0]

    # Base subset: all ligature-input codepoints (ASCII + arrows) that the font
    # actually has, kept in one file so GSUB ligature closures stay intact.
    font_cmap = set(TTFont(font_path).getBestCmap().keys())
    base_cps = BASE_CODEPOINTS & font_cmap

    jobs = []
    if base_cps:
        base_filename = f"{font_basename}.subset.base.woff2"
        base_path = os.path.join(output_dir, base_filename)
        base_range = codepoints_to_range_str(base_cps)
        jobs.append((font_path, base_cps, base_path, 'base', base_range, base_filename))

    for i, range_str in enumerate(ranges):
        codepoints = unicode_range_to_codepoints(range_str)
        # Remove base codepoints so they aren't scattered back into other files.
        codepoints -= base_cps
        if not codepoints:
            continue
        subset_filename = f"{font_basename}.subset.{i}.woff2"
        subset_path = os.path.join(output_dir, subset_filename)
        # Re-derive the unicode-range from the (carved) codepoint set so the CSS
        # matches what the file actually contains.
        carved_range = codepoints_to_range_str(codepoints)
        jobs.append((font_path, codepoints, subset_path, i, carved_range, subset_filename))

    workers = min(cpu_count(), 6)
    pool_args = [(j[0], j[1], j[2]) for j in jobs]

    with Pool(workers) as pool:
        results = pool.map(_subset_one, pool_args)

    css_lines = []
    for job, result in zip(jobs, results):
        if result is None:
            continue
        _, _, _, i, range_str, subset_filename = job
        css_lines.append(f"/* [{i}] */")
        css_lines.append("@font-face {")
        css_lines.append(f"\tfont-family: '{family_name}';")
        css_lines.append(f"\tfont-style: normal;")
        css_lines.append(f"\tfont-display: swap;")
        css_lines.append(f"\tfont-weight: 100 900;")
        css_lines.append(f"\tsrc: url('./{subset_filename}') format('woff2');")
        css_lines.append(f"\tunicode-range: {range_str};")
        css_lines.append("}")

    css_path = os.path.join(output_dir, css_filename)
    with open(css_path, 'w') as f:
        f.write('\n'.join(css_lines) + '\n')

    subset_count = len([f for f in os.listdir(output_dir) if f.endswith('.woff2')])
    print(f"  Done: {subset_count} subsets ({workers} workers), CSS at {css_filename}")


if __name__ == "__main__":
    font_path = sys.argv[1]
    reference_css = sys.argv[2]
    output_dir = sys.argv[3]
    family_name = sys.argv[4] if len(sys.argv) > 4 else "Inter CJK Variable"
    css_filename = sys.argv[5] if len(sys.argv) > 5 else "inter-cjk-dynamic-subset.css"

    print(f"Generating dynamic subsets for {os.path.basename(font_path)}:")
    generate(font_path, reference_css, output_dir, family_name, css_filename)
