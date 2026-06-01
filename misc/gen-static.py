"""Generate static font instances from a single opsz+wght variable TTF."""
import sys
import os
from multiprocessing import Pool, cpu_count
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
    (14.0, "InterCJK", "Inter CJK"),
    (32.0, "InterCJKDisplay", "Inter CJK Display"),
]


def _generate_one(args):
    variable_ttf, out_dir, opsz_val, prefix, family_name, weight_name, weight_value = args

    font = TTFont(variable_ttf)
    # Keep GDEF through instancing: its VarStore holds the GPOS anchor deltas, so
    # the instancer needs it to interpolate mark/cursive anchors to this weight.
    # Deleting it first freezes every anchor at the default master, and also
    # leaves GPOS lookups with dangling UseMarkFilteringSet references.
    for tag in ['MVAR', 'HVAR']:
        if tag in font:
            del font[tag]
    instance = instantiateVariableFont(font, {"opsz": opsz_val, "wght": weight_value}, inplace=True, overlap=True)

    for tag in ['fvar', 'STAT', 'gvar', 'avar', 'HVAR', 'MVAR']:
        if tag in instance:
            del instance[tag]

    name_table = instance['name']
    subfamily = "Regular" if weight_name == "Regular" else weight_name
    full_name = f"{family_name} {weight_name}" if weight_name != "Regular" else family_name
    ps_name = f"{prefix}-{weight_name}"

    for record in name_table.names:
        try:
            record.toUnicode()
        except:
            continue
        if record.nameID == 1:
            name_table.setName(family_name, record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 2:
            name_table.setName(subfamily, record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 4:
            name_table.setName(full_name, record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 6:
            name_table.setName(ps_name, record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 3:
            name_table.setName(f"1.000;{ps_name}", record.nameID, record.platformID, record.platEncID, record.langID)

    instance['OS/2'].usWeightClass = weight_value

    out_path = os.path.join(out_dir, f"{prefix}-{weight_name}.ttf")
    instance.save(out_path)

    otf_dir = os.path.join(out_dir, "..", "otf")
    os.makedirs(otf_dir, exist_ok=True)
    otf_path = os.path.join(otf_dir, f"{prefix}-{weight_name}.otf")
    instance.flavor = None
    instance.save(otf_path)

    return f"{prefix}-{weight_name}.ttf ({os.path.getsize(out_path) / 1024:.0f} KB)"


def main():
    variable_ttf = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    jobs = []
    for opsz_val, prefix, family_name in FAMILIES:
        for weight_name, weight_value in WEIGHTS:
            jobs.append((variable_ttf, out_dir, opsz_val, prefix, family_name, weight_name, weight_value))

    workers = min(cpu_count(), 6)
    print(f"Generating {len(jobs)} static instances ({workers} parallel workers):")

    with Pool(workers) as pool:
        for result in pool.imap_unordered(_generate_one, jobs):
            print(f"  {result}")


if __name__ == "__main__":
    main()
