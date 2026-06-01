"""Generate dynamic subset woff2 files and CSS for the STATIC families.

Unlike gen-dynamic-subset.py (which splits the single variable font with
font-weight: 100 900), this splits every static weight separately and emits
one CSS per family, each @font-face carrying its real font-weight value.

Input is the directory of static TTFs produced by gen-static.py, e.g.
  InterCJK-Regular.ttf, InterCJK-Bold.ttf, ..., InterCJKDisplay-Black.ttf

Output (into output_dir):
  InterCJK-Regular.subset.0.woff2, ...           (one set per weight)
  InterCJKDisplay-Bold.subset.5.woff2, ...
  inter-cjk-dynamic-subset.css                   (family "Inter CJK")
  inter-cjk-display-dynamic-subset.css           (family "Inter CJK Display")
"""
import sys
import os
import re
from multiprocessing import Pool, cpu_count
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

WEIGHTS = [
    ("Thin", 100),
    ("ExtraLight", 200),
    ("Light", 300),
    ("Regular", 400),
    ("Medium", 500),
    ("SemiBold", 600),
    ("Bold", 700),
    ("ExtraBold", 800),
    ("Black", 900),
]

# prefix -> (family_name, css_filename)
FAMILIES = [
    ("InterCJK", "Inter CJK", "inter-cjk-dynamic-subset.css"),
    ("InterCJKDisplay", "Inter CJK Display", "inter-cjk-display-dynamic-subset.css"),
]


def parse_unicode_ranges(css_path):
    with open(css_path) as f:
        content = f.read()
    return re.findall(r'unicode-range:\s*([^;]+);', content)


def unicode_range_to_codepoints(range_str):
    codepoints = set()
    for part in range_str.split(','):
        part = part.strip().replace('U+', '').replace('u+', '')
        if '-' in part:
            start, end = part.split('-')
            codepoints.update(range(int(start, 16), int(end, 16) + 1))
        else:
            codepoints.add(int(part, 16))
    return codepoints


# See gen-dynamic-subset.py: ligature input glyphs (calt/dlig/rlig) must stay in
# one woff2 or multi-character ligatures (-> => <= |> fi ...) silently break.
# Keep the ASCII block + arrows together in a per-weight "base" subset.
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


def generate(ttf_dir, reference_css, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    ranges = parse_unicode_ranges(reference_css)

    # Build every (font, range) job, tagged with family/weight for CSS grouping.
    jobs = []
    for prefix, family_name, css_filename in FAMILIES:
        for weight_name, weight_value in WEIGHTS:
            font_path = os.path.join(ttf_dir, f"{prefix}-{weight_name}.ttf")
            if not os.path.exists(font_path):
                continue
            font_basename = f"{prefix}-{weight_name}"
            base_cps = BASE_CODEPOINTS & set(TTFont(font_path).getBestCmap().keys())
            # Base subset: ligature inputs kept together so GSUB closures survive.
            if base_cps:
                base_filename = f"{font_basename}.subset.base.woff2"
                base_path = os.path.join(output_dir, base_filename)
                base_range = codepoints_to_range_str(base_cps)
                jobs.append((font_path, base_cps, base_path,
                             prefix, weight_value, 'base', base_range, base_filename))
            for i, range_str in enumerate(ranges):
                codepoints = unicode_range_to_codepoints(range_str)
                # Carve out base codepoints so they aren't scattered into other files.
                codepoints -= base_cps
                if not codepoints:
                    continue
                subset_filename = f"{font_basename}.subset.{i}.woff2"
                subset_path = os.path.join(output_dir, subset_filename)
                carved_range = codepoints_to_range_str(codepoints)
                jobs.append((font_path, codepoints, subset_path,
                             prefix, weight_value, i, carved_range, subset_filename))

    workers = min(cpu_count(), 6)
    print(f"Generating static dynamic subsets ({len(jobs)} jobs, {workers} workers):")
    pool_args = [(j[0], j[1], j[2]) for j in jobs]
    with Pool(workers) as pool:
        results = pool.map(_subset_one, pool_args)

    # Group CSS lines per family, preserving weight then subset-index order.
    css_by_family = {prefix: [] for prefix, _, _ in FAMILIES}
    for job, result in zip(jobs, results):
        if result is None:
            continue
        _, _, _, prefix, weight_value, i, range_str, subset_filename = job
        css_by_family[prefix].append((weight_value, i, range_str, subset_filename))

    for prefix, family_name, css_filename in FAMILIES:
        entries = css_by_family[prefix]
        if not entries:
            continue
        entries.sort(key=lambda e: (e[0], -1 if e[1] == 'base' else e[1]))
        lines = []
        for weight_value, i, range_str, subset_filename in entries:
            lines.append(f"/* {prefix} {weight_value} [{i}] */")
            lines.append("@font-face {")
            lines.append(f"\tfont-family: '{family_name}';")
            lines.append("\tfont-style: normal;")
            lines.append("\tfont-display: swap;")
            lines.append(f"\tfont-weight: {weight_value};")
            lines.append(f"\tsrc: url('./{subset_filename}') format('woff2');")
            lines.append(f"\tunicode-range: {range_str};")
            lines.append("}")
        css_path = os.path.join(output_dir, css_filename)
        with open(css_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        print(f"  {family_name}: {len(entries)} @font-face -> {css_filename}")

    subset_count = len([f for f in os.listdir(output_dir) if f.endswith('.woff2')])
    print(f"  Done: {subset_count} subset woff2 files")


if __name__ == "__main__":
    ttf_dir = sys.argv[1]
    reference_css = sys.argv[2]
    output_dir = sys.argv[3]
    generate(ttf_dir, reference_css, output_dir)
