"""Convert static TTF instances to proper OTF (CFF outlines).

Takes a directory of static .ttf files (produced by gen-static.py) and
converts each to .otf with PostScript cubic outlines using Qu2CuPen.

Usage:
    python3 misc/gen-otf.py <ttf_dir> <otf_dir>
"""
import sys
import os
from multiprocessing import Pool, cpu_count
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.qu2cuPen import Qu2CuPen

TTF_TABLES = ["glyf", "cvt ", "loca", "fpgm", "prep", "gasp", "LTSH", "hdmx"]


def build_font_info(font):
    """Extract CFF fontInfo dict from name table."""
    name = font["name"]
    info = {}
    full_name = name.getDebugName(4)
    if full_name:
        info["FullName"] = full_name
    family = name.getDebugName(1)
    if family:
        info["FamilyName"] = family
    return info


def convert_one(args):
    """Convert a single TTF to OTF."""
    ttf_path, otf_path, tolerance = args

    try:
        font = TTFont(ttf_path)
        upem = font["head"].unitsPerEm
        glyph_set = font.getGlyphSet()
        charstrings = {}

        for glyph_name in font.getGlyphOrder():
            glyph = glyph_set[glyph_name]
            width = glyph.width

            try:
                t2_pen = T2CharStringPen(width=width, glyphSet=None)
                qu2cu_pen = Qu2CuPen(
                    t2_pen,
                    max_err=tolerance,
                    all_cubic=True,
                    reverse_direction=True,
                )
                glyph.draw(qu2cu_pen)
                charstrings[glyph_name] = t2_pen.getCharString()
            except NotImplementedError:
                t2_pen = T2CharStringPen(width=width, glyphSet=None)
                glyph.draw(t2_pen)
                charstrings[glyph_name] = t2_pen.getCharString()

        ps_name = font["name"].getDebugName(6) or "Unknown"
        font_info = build_font_info(font)

        fb = FontBuilder(font=font)
        fb.isTTF = False

        for table in TTF_TABLES:
            if table in fb.font:
                del fb.font[table]

        fb.setupGlyphOrder(font.getGlyphOrder())
        fb.setupCFF(
            psName=ps_name,
            charStringsDict=charstrings,
            fontInfo=font_info,
            privateDict={},
        )

        metrics = {}
        for glyph_name in fb.font.getGlyphOrder():
            cs = charstrings.get(glyph_name)
            if cs is not None:
                cs.recalcBounds(charstrings)
                bounds = cs.calcBounds(charstrings)
                width = cs.width
                lsb = int(bounds[0]) if bounds else 0
            else:
                width = 0
                lsb = 0
            metrics[glyph_name] = (width, lsb)
        fb.setupHorizontalMetrics(metrics)
        fb.setupMaxp()

        fb.font.save(otf_path)
        size_kb = os.path.getsize(otf_path) / 1024
        basename = os.path.basename(otf_path)
        return f"{basename} ({size_kb:.0f} KB)"

    except Exception as e:
        basename = os.path.basename(ttf_path)
        return f"{basename} FAILED: {e}"


def main():
    ttf_dir = sys.argv[1]
    otf_dir = sys.argv[2]
    tolerance = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    os.makedirs(otf_dir, exist_ok=True)

    ttf_files = sorted(f for f in os.listdir(ttf_dir) if f.endswith(".ttf"))
    if not ttf_files:
        print(f"No .ttf files found in {ttf_dir}")
        sys.exit(1)

    jobs = []
    for filename in ttf_files:
        ttf_path = os.path.join(ttf_dir, filename)
        otf_filename = filename.replace(".ttf", ".otf")
        otf_path = os.path.join(otf_dir, otf_filename)
        jobs.append((ttf_path, otf_path, tolerance))

    workers = min(cpu_count(), 6)
    print(f"Converting {len(jobs)} TTF → OTF ({workers} parallel workers):")

    with Pool(workers) as pool:
        for result in pool.imap_unordered(convert_one, jobs):
            print(f"  {result}")

    otf_count = len([f for f in os.listdir(otf_dir) if f.endswith(".otf")])
    print(f"  Done: {otf_count} OTF files")


if __name__ == "__main__":
    main()
