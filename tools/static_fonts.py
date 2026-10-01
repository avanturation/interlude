"""Generate static font instances from a single opsz+wght variable TTF."""
import sys
import argparse, hashlib, json, shutil
import os
from multiprocessing import Pool, cpu_count
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

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

FAMILIES = [
    (14.0, "Interlude", "Interlude"),
    (32.0, "InterludeDisplay", "Interlude Display"),
]

WIDTHS = [
    ("Condensed", 75, 3),
    ("", 100, 5),
    ("Expanded", 125, 7),
]


def _generate_one(args):
    (variable_ttf, out_dir, opsz_val, prefix, family_name,
     weight_name, weight_value, width_label, width_value, width_class) = args

    target = Path(out_dir) / f"{prefix}{width_label}-{weight_name}.ttf"
    if target.exists():
        return f"{target.name} (cached)"
    font = TTFont(variable_ttf)
    # Keep GDEF through instancing: its VarStore holds the GPOS anchor deltas, so
    # the instancer needs it to interpolate mark/cursive anchors to this weight.
    # Deleting it first freezes every anchor at the default master, and also
    # leaves GPOS lookups with dangling UseMarkFilteringSet references.
    axis_tags = {a.axisTag for a in font['fvar'].axes}
    pins = {"opsz": opsz_val, "wght": weight_value}
    if "wdth" in axis_tags:
        pins["wdth"] = width_value
    instance = instantiateVariableFont(font, pins, inplace=True, overlap=True)

    for tag in ['fvar', 'STAT', 'gvar', 'avar', 'HVAR', 'MVAR']:
        if tag in instance:
            del instance[tag]

    name_table = instance['name']
    wfam = f"{family_name} {width_label}".strip()
    wps_prefix = f"{prefix}{width_label}"
    typo_subfamily = f"{width_label} {weight_name}".strip()
    is_bold = weight_value == 700
    ribbi_subfamily = "Bold" if is_bold else "Regular"
    legacy_family = wfam if weight_value in (400,700) else f"{wfam} {weight_name}"
    full_name = f"{wfam} {weight_name}" if weight_name != "Regular" else wfam
    ps_name = f"{wps_prefix}-{weight_name}"

    for record in name_table.names:
        try:
            record.toUnicode()
        except Exception:
            continue
        if record.nameID == 1:
            name_table.setName(legacy_family, record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 2:
            name_table.setName(ribbi_subfamily, record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 4:
            name_table.setName(full_name, record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 6:
            name_table.setName(ps_name, record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 3:
            name_table.setName(f"{Path(__file__).resolve().parents[1].joinpath('version.txt').read_text().strip()};{ps_name}", record.nameID, record.platformID, record.platEncID, record.langID)

    instance['OS/2'].usWeightClass = weight_value
    instance['OS/2'].usWidthClass = width_class

    os2 = instance['OS/2']
    head = instance['head']
    if is_bold:
        os2.fsSelection = (os2.fsSelection | 0x0020) & ~0x0040  # BOLD on, REGULAR off
        head.macStyle |= 0x0001  # bold bit
    else:
        os2.fsSelection = (os2.fsSelection | 0x0040) & ~0x0020  # REGULAR on, BOLD off
        head.macStyle &= ~0x0001
    os2.fsSelection |= 0x0100  # WWS bit: family differs only by weight/width/slope

    name_table.setName(family_name, 16, 3, 1, 0x0409)
    name_table.setName(typo_subfamily, 17, 3, 1, 0x0409)
    name_table.setName(family_name, 16, 1, 0, 0)
    name_table.setName(typo_subfamily, 17, 1, 0, 0)

    out_path = os.path.join(out_dir, f"{ps_name}.ttf")
    instance.save(out_path)

    return f"{ps_name}.ttf ({os.path.getsize(out_path) / 1024:.0f} KB)"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('variable_ttf');parser.add_argument('out_dir')
    parser.add_argument('--web-only',action='store_true');parser.add_argument('--jobs',type=int,default=2)
    args=parser.parse_args();variable_ttf=args.variable_ttf;out_dir=args.out_dir
    key=hashlib.sha256(Path(variable_ttf).read_bytes()+Path(__file__).read_bytes()).hexdigest()
    marker=Path(out_dir)/'.input-sha256'
    if marker.exists() and marker.read_text()!=key:shutil.rmtree(out_dir)
    os.makedirs(out_dir,exist_ok=True);marker.write_text(key)

    jobs = []
    for opsz_val, prefix, family_name in FAMILIES:
        for width_label, width_value, width_class in WIDTHS:
            if args.web_only and width_value != 100:continue
            for weight_name, weight_value in WEIGHTS:
                jobs.append((variable_ttf, out_dir, opsz_val, prefix, family_name,
                             weight_name, weight_value, width_label, width_value, width_class))

    workers = max(1,min(cpu_count(), args.jobs))
    print(f"Generating {len(jobs)} static instances ({workers} parallel workers):")

    with Pool(workers) as pool:
        for result in pool.imap_unordered(_generate_one, jobs):
            print(f"  {result}")


if __name__ == "__main__":
    main()
