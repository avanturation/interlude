"""Merge Inter Variable + Pretendard JP Variable into Interlude Variable.

Applies all design adjustments:
- CJK vertical alignment: Y offset +21 (matches Pretendard's 가-H center diff of +3)
- CJK weight matching: 1% horizontal thinning (gray-level balance with Latin)
- CJK optical size: 3% tighter at opsz=32 (Display)
- Contextual symbol alignment: CJK added to calt @UC class so symbols get .case forms
- Latin-CJK kern: +100 units between script transitions
- SUIT-matched vertical metrics: ratio 1.248, symmetric around cap center
- GSUB/GPOS: CJK script support (hang, kana, hani)
"""
import sys
import os
import copy
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import NamedInstance


def _read_version():
    """Read the release version from version.txt (repo root), default '0.0.0'."""
    path = os.path.join(os.path.dirname(__file__), "..", "version.txt")
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def _version_to_revision(version):
    """head.fontRevision as major.minor float, e.g. '1.0.1' -> 1.0 (matches name ID 5 major.minor)."""
    parts = version.split(".")
    major = int(parts[0]) if parts and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return float(f"{major}.{minor}")

Y_OFFSET = 21
CJK_HSCALE = 0.99
OPSZ_SCALE = 0.03

CJK_RANGES = [
    (0x1100, 0x11FF), (0x2E80, 0x2EFF), (0x2F00, 0x2FDF),
    (0x3000, 0x303F), (0x3040, 0x309F), (0x30A0, 0x30FF),
    (0x3100, 0x312F), (0x3130, 0x318F), (0x31F0, 0x31FF),
    (0x3200, 0x32FF), (0x3300, 0x33FF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xA960, 0xA97F), (0xAC00, 0xD7AF),
    (0xD7B0, 0xD7FF), (0xF900, 0xFAFF), (0xFE30, 0xFE4F),
    (0xFF00, 0xFFEF),
]

WEIGHTS = [
    (100, "Thin"), (200, "ExtraLight"), (300, "Light"), (400, "Regular"),
    (500, "Medium"), (600, "SemiBold"), (700, "Bold"), (800, "ExtraBold"),
    (900, "Black"),
]


def get_deps(gname, glyf_table, visited=None):
    if visited is None:
        visited = set()
    if gname in visited:
        return visited
    visited.add(gname)
    g = glyf_table[gname]
    if g.isComposite():
        for c in g.components:
            get_deps(c.glyphName, glyf_table, visited)
    return visited


def merge(inter_ttf, pretendard_ttf, output_path):
    print("Loading Inter Variable...")
    inter = TTFont(inter_ttf)
    _ = inter['gvar'].variations

    print("Loading Pretendard JP Variable...")
    pretendard = TTFont(pretendard_ttf)
    _ = pretendard['gvar'].variations
    pretendard_cmap = pretendard.getBestCmap()
    pretendard_glyf = pretendard['glyf']
    pretendard_hmtx = pretendard['hmtx']
    pretendard_gvar = pretendard['gvar'].variations

    inter_cmap = inter.getBestCmap()
    inter_glyf = inter['glyf']
    inter_hmtx = inter['hmtx']

    # Identify CJK codepoints to add
    new_codepoints = set()
    for start, end in CJK_RANGES:
        for cp in range(start, end + 1):
            if cp in pretendard_cmap and cp not in inter_cmap:
                new_codepoints.add(cp)
    print(f"  {len(new_codepoints)} CJK codepoints to add")

    # Get glyph dependencies
    inter_glyph_set = set(inter.getGlyphOrder())
    glyphs_needed = set()
    for cp in new_codepoints:
        glyphs_needed.update(get_deps(pretendard_cmap[cp], pretendard_glyf))
    glyphs_to_copy = sorted(glyphs_needed - inter_glyph_set)
    print(f"  {len(glyphs_to_copy)} glyphs to copy")

    # Name mapping
    name_map = {g: (f"jp.{g}" if g in inter_glyph_set else g) for g in glyphs_to_copy}

    # Add to glyph order
    glyph_order = inter.getGlyphOrder()
    # Boundary between original Inter glyphs and the appended CJK glyphs.
    # Captured from the live font (not a hardcoded 2937) so a future Inter
    # version with a different glyph count doesn't silently mis-slice the
    # CJK glyph set used for calt/rlig context and Latin-CJK kern.
    inter_glyph_count = len(glyph_order)
    for gname in glyphs_to_copy:
        glyph_order.append(name_map[gname])
    inter.setGlyphOrder(glyph_order)

    # Copy glyphs with adjustments
    print("  Copying glyphs (Y offset, horizontal scaling)...")
    for gname in glyphs_to_copy:
        target = name_map[gname]
        g = copy.deepcopy(pretendard_glyf[gname])
        width = pretendard_hmtx[gname][0]
        x_center = width / 2.0

        if g.isComposite():
            for comp in g.components:
                if comp.glyphName in name_map:
                    comp.glyphName = name_map[comp.glyphName]
                if hasattr(comp, 'y'):
                    comp.y += Y_OFFSET
        elif g.numberOfContours > 0:
            coords = g.coordinates
            if coords:
                new_coords = [(round(x_center + (x - x_center) * CJK_HSCALE), y + Y_OFFSET)
                              for x, y in coords]
                g.coordinates = type(coords)(new_coords)

        if hasattr(g, 'yMin') and g.yMin is not None:
            g.yMin += Y_OFFSET
            g.yMax += Y_OFFSET

        inter_glyf[target] = g
        inter_hmtx[target] = pretendard_hmtx[gname]

    # Update cmap
    for table in inter['cmap'].tables:
        if hasattr(table, 'cmap') and table.cmap is not None:
            for cp in new_codepoints:
                orig = pretendard_cmap[cp]
                target = name_map.get(orig, orig)
                if target in set(inter.getGlyphOrder()):
                    table.cmap[cp] = target

    # Add CJK gvar (wght + opsz)
    print("  Adding CJK gvar (wght + opsz)...")
    inter_gvar = inter['gvar']
    for gname in glyphs_to_copy:
        target = name_map[gname]
        variations = []

        # wght variation from Pretendard
        if gname in pretendard_gvar and pretendard_gvar[gname]:
            for tv in pretendard_gvar[gname]:
                if 'wght' in tv.axes:
                    new_coords = []
                    for coord in tv.coordinates:
                        if coord is None:
                            new_coords.append(None)
                        else:
                            new_coords.append((round(coord[0] * CJK_HSCALE), coord[1]))
                    variations.append(TupleVariation({'wght': tv.axes['wght']}, new_coords))

        # opsz variation (3% tighter at Display)
        g = inter_glyf[target]
        if not g.isComposite() and g.numberOfContours > 0:
            coords = g.coordinates
            if coords:
                width = inter_hmtx[target][0]
                xc = width / 2.0
                opsz_deltas = [(round((x - xc) * (-OPSZ_SCALE)), 0) for x, y in coords]
                adv_delta = round(width * (-OPSZ_SCALE))
                opsz_deltas += [(0, 0), (adv_delta, 0), (0, 0), (0, 0)]
                variations.append(TupleVariation({'opsz': (0, 1.0, 1.0)}, opsz_deltas))

        inter_gvar.variations[target] = variations

    # Add CJK contextual symbol alignment via calt feature
    print("  Adding calt: CJK-context symbol .case substitution...")
    gsub = inter['GSUB'].table
    cjk_glyph_list = sorted(set(glyph_order[inter_glyph_count:]), key=lambda g: glyph_order.index(g))

    # Get case mapping: find all glyph.case pairs in the font
    case_mapping = {}
    for g in glyph_order:
        if '.case' in g and '.case.' not in g:
            base = g.replace('.case', '')
            if base in set(glyph_order):
                case_mapping[base] = g

    # Create SingleSubst lookup for case substitution
    single_st = otTables.SingleSubst()
    single_st.mapping = case_mapping
    single_lookup = otTables.Lookup()
    single_lookup.LookupType = 1
    single_lookup.LookupFlag = 0
    single_lookup.SubTable = [single_st]
    single_lookup.SubTableCount = 1
    single_idx = len(gsub.LookupList.Lookup)
    gsub.LookupList.Lookup.append(single_lookup)

    # Create ChainContextSubst: [CJK] symbol' → .case
    input_glyphs = sorted(case_mapping.keys(), key=lambda g: glyph_order.index(g) if g in glyph_order else 999999)

    chain_st1 = otTables.ChainContextSubst()
    chain_st1.Format = 3
    bt_cov = otTables.Coverage()
    bt_cov.Format = 1
    bt_cov.glyphs = cjk_glyph_list
    chain_st1.BacktrackCoverage = [bt_cov]
    chain_st1.BacktrackCount = 1
    in_cov = otTables.Coverage()
    in_cov.Format = 1
    in_cov.glyphs = input_glyphs
    chain_st1.InputCoverage = [in_cov]
    chain_st1.InputCount = 1
    chain_st1.LookAheadCoverage = []
    chain_st1.LookAheadCount = 0
    slr1 = otTables.SubstLookupRecord()
    slr1.SequenceIndex = 0
    slr1.LookupListIndex = single_idx
    chain_st1.SubstLookupRecord = [slr1]
    chain_st1.SubstCount = 1

    # ChainContextSubst: symbol' [CJK] → .case
    chain_st2 = copy.deepcopy(chain_st1)
    chain_st2.BacktrackCoverage = []
    chain_st2.BacktrackCount = 0
    la_cov = otTables.Coverage()
    la_cov.Format = 1
    la_cov.glyphs = cjk_glyph_list
    chain_st2.LookAheadCoverage = [la_cov]
    chain_st2.LookAheadCount = 1

    chain_lookup = otTables.Lookup()
    chain_lookup.LookupType = 6
    chain_lookup.LookupFlag = 0
    chain_lookup.SubTable = [chain_st1, chain_st2]
    chain_lookup.SubTableCount = 2
    chain_idx = len(gsub.LookupList.Lookup)
    gsub.LookupList.Lookup.append(chain_lookup)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)

    # Append to existing calt feature
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == 'calt':
            fr.Feature.LookupListIndex.append(chain_idx)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
            break

    # Also register as rlig (harfbuzz Hangul shaper skips calt but processes rlig)
    rlig_fr = otTables.FeatureRecord()
    rlig_fr.FeatureTag = 'rlig'
    rlig_fr.Feature = otTables.Feature()
    rlig_fr.Feature.LookupListIndex = [chain_idx]
    rlig_fr.Feature.LookupCount = 1
    rlig_fr.Feature.FeatureParams = None
    rlig_idx = len(gsub.FeatureList.FeatureRecord)
    gsub.FeatureList.FeatureRecord.append(rlig_fr)
    gsub.FeatureList.FeatureCount = len(gsub.FeatureList.FeatureRecord)

    for sr in gsub.ScriptList.ScriptRecord:
        if sr.Script.DefaultLangSys:
            sr.Script.DefaultLangSys.FeatureIndex.append(rlig_idx)
            sr.Script.DefaultLangSys.FeatureCount = len(sr.Script.DefaultLangSys.FeatureIndex)

    print(f"    {len(case_mapping)} symbol→.case pairs via calt+rlig")

    # Replace ₩ with Pretendard's Korean-style won sign
    print("  Replacing ₩ with Pretendard glyph...")
    won_cp = 0x20A9
    if won_cp in pretendard_cmap:
        p_won_name = pretendard_cmap[won_cp]
        i_won_name = inter.getBestCmap()[won_cp]
        g = copy.deepcopy(pretendard_glyf[p_won_name])
        width = pretendard_hmtx[p_won_name][0]
        x_center = width / 2.0
        if g.numberOfContours > 0 and g.coordinates:
            new_coords = [(round(x_center + (x - x_center) * CJK_HSCALE), y + Y_OFFSET)
                          for x, y in g.coordinates]
            g.coordinates = type(g.coordinates)(new_coords)
        if hasattr(g, 'yMin') and g.yMin is not None:
            g.yMin += Y_OFFSET
            g.yMax += Y_OFFSET
        inter_glyf[i_won_name] = g
        inter_hmtx[i_won_name] = pretendard_hmtx[p_won_name]
        if p_won_name in pretendard_gvar and pretendard_gvar[p_won_name]:
            won_variations = []
            for tv in pretendard_gvar[p_won_name]:
                if 'wght' in tv.axes:
                    won_variations.append(TupleVariation({'wght': tv.axes['wght']}, tv.coordinates))
            inter_gvar.variations[i_won_name] = won_variations

    # GSUB/GPOS scripts
    print("  Adding CJK scripts to GSUB/GPOS...")
    for table_tag in ['GSUB', 'GPOS']:
        if table_tag in inter:
            table = inter[table_tag].table
            if table.ScriptList:
                existing = {s.ScriptTag for s in table.ScriptList.ScriptRecord}
                dflt = None
                for sr in table.ScriptList.ScriptRecord:
                    if sr.ScriptTag == 'DFLT':
                        dflt = sr.Script
                        break
                for tag in ['kana', 'hani']:
                    if tag not in existing:
                        nr = otTables.ScriptRecord()
                        nr.ScriptTag = tag
                        nr.Script = otTables.Script()
                        nr.Script.DefaultLangSys = copy.deepcopy(dflt.DefaultLangSys) if dflt else None
                        nr.Script.LangSysRecord = []
                        nr.Script.LangSysCount = 0
                        table.ScriptList.ScriptRecord.append(nr)
                table.ScriptList.ScriptCount = len(table.ScriptList.ScriptRecord)

    # Vertical metrics (SUIT-matched)
    print("  Setting vertical metrics (ratio 1.125, total=2304)...")
    os2 = inter['OS/2']
    hhea = inter['hhea']
    os2.sTypoAscender = 2024
    os2.sTypoDescender = -532
    os2.sTypoLineGap = 0
    os2.fsSelection |= (1 << 7)
    hhea.ascent = 2024
    hhea.descent = -532
    hhea.lineGap = 0

    glyf_table = inter['glyf']
    y_max = max((glyf_table[g].yMax for g in inter.getGlyphOrder() if hasattr(glyf_table.get(g), 'yMax') and glyf_table[g].yMax is not None), default=2024)
    y_min = min((glyf_table[g].yMin for g in inter.getGlyphOrder() if hasattr(glyf_table.get(g), 'yMin') and glyf_table[g].yMin is not None), default=-532)
    os2.usWinAscent = max(2024, y_max)
    os2.usWinDescent = max(532, abs(y_min))

    # OS/2 ranges
    os2.ulUnicodeRange1 |= (1 << 28)
    os2.ulUnicodeRange2 |= (1 << 16) | (1 << 17) | (1 << 18) | (1 << 24) | (1 << 27) | (1 << 29)
    os2.ulCodePageRange1 |= (1 << 17) | (1 << 19) | (1 << 20)

    # maxp, HVAR
    inter['maxp'].numGlyphs = len(glyph_order)
    if 'HVAR' in inter:
        del inter['HVAR']

    # Named instances
    print("  Setting font metadata...")
    name_table = inter['name']

    VERSION = _read_version()
    metadata = {
        0: f"Copyright 2016 The Inter Project Authors (https://github.com/rsms/inter)\n"
           f"Copyright 2021 The Pretendard Project Authors (https://github.com/orioncactus/pretendard)\n"
           f"Copyright 2025 The Interlude Project Authors (https://github.com/avanturation/interlude)",
        5: f"Version {VERSION}",
        7: "Interlude is a trademark of the Interlude Project Authors.",
        8: "Interlude Project Authors",
        9: "Rasmus Andersson, Kil Hyung-jin, avanturation",
        10: "Interlude combines Inter and Pretendard JP for seamless Latin-CJK mixed typography.",
        11: "https://github.com/avanturation/interlude",
        12: "https://github.com/avanturation/interlude",
        13: "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
        14: "https://scripts.sil.org/OFL",
    }

    for nid, value in metadata.items():
        for record in name_table.names:
            if record.nameID == nid:
                name_table.setName(value, nid, record.platformID, record.platEncID, record.langID)

    inter['OS/2'].achVendID = "INTL"

    # Add Pretendard ss features (ss05, ss06, ss10-ss16)
    # First, move Inter's ss05(Circled) + ss06(Squared) to ss09
    print("  Moving Inter ss05+ss06 (Circled/Squared) to ss09...")
    gsub_table = inter['GSUB'].table
    ss09_lookups = []
    for fr in gsub_table.FeatureList.FeatureRecord:
        if fr.FeatureTag in ('ss05', 'ss06'):
            ss09_lookups.extend(fr.Feature.LookupListIndex)

    if ss09_lookups:
        ss09_fr = otTables.FeatureRecord()
        ss09_fr.FeatureTag = 'ss09'
        ss09_fr.Feature = otTables.Feature()
        ss09_fr.Feature.LookupListIndex = ss09_lookups
        ss09_fr.Feature.LookupCount = len(ss09_lookups)
        from fontTools.ttLib.tables.otTables import FeatureParamsStylisticSet
        params = FeatureParamsStylisticSet()
        params.Version = 0
        params.UINameID = inter['name'].addName("Circled and Squared Characters")
        ss09_fr.Feature.FeatureParams = params
        feat_idx = len(gsub_table.FeatureList.FeatureRecord)
        gsub_table.FeatureList.FeatureRecord.append(ss09_fr)
        gsub_table.FeatureList.FeatureCount = len(gsub_table.FeatureList.FeatureRecord)
        for sr in gsub_table.ScriptList.ScriptRecord:
            if sr.Script.DefaultLangSys:
                sr.Script.DefaultLangSys.FeatureIndex.append(feat_idx)
                sr.Script.DefaultLangSys.FeatureCount = len(sr.Script.DefaultLangSys.FeatureIndex)

    print("  Adding Pretendard ss features (ss05, ss06, ss10-ss16)...")
    sys.path.insert(0, os.path.dirname(__file__))
    from importlib import import_module
    import importlib.util
    spec = importlib.util.spec_from_file_location("add_ss", os.path.join(os.path.dirname(__file__), "add-ss-features.py"))
    add_ss_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(add_ss_mod)
    add_ss_mod.add_pretendard_ss_features(inter, pretendard, glyph_order)
    add_ss_mod.add_ss05_chain_context(inter, glyph_order, pretendard)

    print("  Setting named instances...")
    for record in name_table.names:
        try:
            record.toUnicode()
        except Exception:
            continue
        if record.nameID == 1:
            name_table.setName("Interlude Variable", record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 4:
            name_table.setName("Interlude Variable", record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 6:
            name_table.setName("Interlude-Variable", record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 3:
            name_table.setName(f"{VERSION};INTL;Interlude-Variable", record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 25:
            name_table.setName("Interlude", record.nameID, record.platformID, record.platEncID, record.langID)

    inter['fvar'].instances = []
    max_nid = max(r.nameID for r in name_table.names)
    nid = max_nid + 1
    for opsz_val in [14.0]:
        for wght_val, wght_name in WEIGHTS:
            inst = NamedInstance()
            inst.subfamilyNameID = nid
            name_table.setName(wght_name, nid, 3, 1, 0x0409)
            name_table.setName(wght_name, nid, 1, 0, 0)
            ps_nid = nid + 100
            ps_name = f"Interlude-{wght_name}" if wght_name != "Regular" else "Interlude-Regular"
            name_table.setName(ps_name, ps_nid, 3, 1, 0x0409)
            inst.postScriptNameID = ps_nid
            inst.coordinates = {"opsz": opsz_val, "wght": float(wght_val)}
            inter['fvar'].instances.append(inst)
            nid += 1

    # Fix xAvgCharWidth (fontbakery expects average of ALL glyph widths)
    cmap_final = inter.getBestCmap()
    all_widths = [inter_hmtx[g][0] for g in inter.getGlyphOrder() if inter_hmtx[g][0] > 0]
    inter['OS/2'].xAvgCharWidth = round(sum(all_widths) / len(all_widths))

    # Fix GDEF: mark uni0488, uni0489 as combining marks (class 3)
    if 'GDEF' in inter:
        gdef = inter['GDEF'].table
        if gdef.GlyphClassDef:
            gdef.GlyphClassDef.classDefs['uni0488'] = 3
            gdef.GlyphClassDef.classDefs['uni0489'] = 3

    # Add ss descriptions (fontbakery stylisticset_description)
    ss_descriptions = {
        'ss05': 'Korean Localization',
        'ss06': 'Pretendard Disambiguation',
        'ss10': 'Medium Symbols',
        'ss11': 'Outlined Symbols',
        'ss12': 'Circled Symbols',
        'ss13': 'Squared Symbols',
        'ss14': 'Filled Symbols',
        'ss15': 'Small Symbols',
        'ss16': 'Large Symbols',
    }
    for fr in inter['GSUB'].table.FeatureList.FeatureRecord:
        if fr.FeatureTag in ss_descriptions:
            from fontTools.ttLib.tables.otTables import FeatureParamsStylisticSet
            params = FeatureParamsStylisticSet()
            params.Version = 0
            params.UINameID = inter['name'].addName(ss_descriptions[fr.FeatureTag])
            fr.Feature.FeatureParams = params


    # Decompose only transformed components (with scale/rotation flags)
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    glyphset = inter.getGlyphSet()
    inter_gvar = inter['gvar']
    decomposed = 0
    for gname in list(inter_glyf.glyphs.keys()):
        g = inter_glyf[gname]
        if not g.isComposite():
            continue
        has_transform = any(
            (comp.flags & 0x0008) or (comp.flags & 0x0040) or (comp.flags & 0x0080)
            for comp in g.components
        )
        if not has_transform:
            continue
        try:
            rec = DecomposingRecordingPen(glyphset)
            glyphset[gname].draw(rec)
            if not any(op == 'addComponent' for op, _ in rec.value):
                pen = TTGlyphPen(None)
                rec.replay(pen)
                new_g = pen.glyph()
                if not new_g.isComposite():
                    inter_glyf.glyphs[gname] = new_g
                    inter_gvar.variations[gname] = []
                    decomposed += 1
        except Exception:
            pass
    print(f"  Decomposed {decomposed} transformed components")

    # Sort GSUB/GPOS feature and script records alphabetically (OTS requirement)
    for table_tag in ['GSUB', 'GPOS']:
        if table_tag in inter:
            table = inter[table_tag].table
            if table.ScriptList:
                table.ScriptList.ScriptRecord.sort(key=lambda r: r.ScriptTag)
                table.ScriptList.ScriptCount = len(table.ScriptList.ScriptRecord)
            if table.FeatureList:
                records = table.FeatureList.FeatureRecord
                # Build the remap from the ORIGINAL order, before reordering, so
                # idx_map[old_position] -> new_position. Computing it after the
                # in-place sort would yield a useless identity map.
                order = sorted(range(len(records)), key=lambda i: records[i].FeatureTag)
                idx_map = {old: new for new, old in enumerate(order)}
                table.FeatureList.FeatureRecord = [records[i] for i in order]
                table.FeatureList.FeatureCount = len(table.FeatureList.FeatureRecord)

                def _remap_langsys(langsys):
                    if langsys:
                        langsys.FeatureIndex = sorted(idx_map[i] for i in langsys.FeatureIndex)
                        langsys.FeatureCount = len(langsys.FeatureIndex)

                # Remap every LangSys: default AND non-default (e.g. latn ROM/CAT/MOL),
                # otherwise those language systems point at the wrong feature tags.
                for sr in table.ScriptList.ScriptRecord:
                    _remap_langsys(sr.Script.DefaultLangSys)
                    for lsr in (sr.Script.LangSysRecord or []):
                        _remap_langsys(lsr.LangSys)

    # Sort all GSUB/GPOS coverages by glyph order to suppress fonttools warning
    glyph_to_idx = {g: i for i, g in enumerate(inter.getGlyphOrder())}
    for table_tag in ['GSUB', 'GPOS']:
        if table_tag in inter:
            for lookup in inter[table_tag].table.LookupList.Lookup:
                for st in lookup.SubTable:
                    for attr in ['Coverage', 'BacktrackCoverage', 'InputCoverage', 'LookAheadCoverage']:
                        covs = getattr(st, attr, None)
                        if covs is None:
                            continue
                        if not isinstance(covs, list):
                            covs = [covs]
                        for cov in covs:
                            if hasattr(cov, 'glyphs') and cov.glyphs:
                                cov.glyphs = sorted(cov.glyphs, key=lambda g: glyph_to_idx.get(g, 999999))

    # Shorten glyph names > 31 chars (fontbakery valid_glyphnames)
    final_order = inter.getGlyphOrder()
    rename_map = {}
    for g in final_order:
        if len(g) > 31:
            short = g[:28] + g[-3:]
            rename_map[g] = short
    if rename_map:
        for old, new in rename_map.items():
            if old in inter_glyf.glyphs:
                inter_glyf.glyphs[new] = inter_glyf.glyphs.pop(old)
            if old in inter_hmtx.metrics:
                inter_hmtx.metrics[new] = inter_hmtx.metrics.pop(old)
            if old in inter_gvar.variations:
                inter_gvar.variations[new] = inter_gvar.variations.pop(old)
        final_order = [rename_map.get(g, g) for g in final_order]
        inter.setGlyphOrder(final_order)
        for lookup in inter['GSUB'].table.LookupList.Lookup:
            for st in lookup.SubTable:
                if hasattr(st, 'mapping'):
                    st.mapping = {rename_map.get(s, s): rename_map.get(d, d) for s, d in st.mapping.items()}

    # Fix font_version mismatch (head.fontRevision must match name ID 5)
    inter['head'].fontRevision = _version_to_revision(VERSION)


    # Add smart dropout control (fontbakery smart_dropout)
    from fontTools.ttLib.tables._g_a_s_p import table__g_a_s_p
    gasp = table__g_a_s_p()
    gasp.version = 1
    gasp.gaspRange = {0xFFFF: 0x000F}
    inter['gasp'] = gasp

    from fontTools.ttLib.tables._p_r_e_p import table__p_r_e_p
    from fontTools.ttLib.tables.ttProgram import Program
    prep = table__p_r_e_p()
    prep.program = Program()
    prep.program.fromAssembly(['PUSHW[]', '511', 'SCANCTRL[]', 'PUSHB[]', '4', 'SCANTYPE[]'])
    inter['prep'] = prep

    # Fix STAT table (add axis values for fvar/STAT consistency)
    if 'STAT' in inter:
        stat = inter['STAT'].table
        stat.DesignAxisRecord.Axis = [a for a in stat.DesignAxisRecord.Axis if a.AxisTag != 'ital']
        stat.DesignAxisCount = len(stat.DesignAxisRecord.Axis)
        stat.AxisValueArray = otTables.AxisValueArray()
        stat.AxisValueArray.AxisValue = []

        av_text = otTables.AxisValue()
        av_text.Format = 1
        av_text.AxisIndex = 0
        av_text.Flags = 2  # elidable (default)
        av_text.Value = 14.0
        av_text.ValueNameID = inter['name'].addName("Text")
        stat.AxisValueArray.AxisValue.append(av_text)

        av_display = otTables.AxisValue()
        av_display.Format = 1
        av_display.AxisIndex = 0
        av_display.Flags = 0
        av_display.Value = 32.0
        av_display.ValueNameID = inter['name'].addName("Display")
        stat.AxisValueArray.AxisValue.append(av_display)

        for wght_val, wght_name in WEIGHTS:
            av = otTables.AxisValue()
            av.Format = 1
            av.AxisIndex = 1
            av.Flags = 2 if wght_val == 400 else 0
            av.Value = float(wght_val)
            av.ValueNameID = inter['name'].addName(wght_name)
            stat.AxisValueArray.AxisValue.append(av)

    # Remove Mac name entries (fontbakery no_mac_entries) — must be last before save
    inter['name'].names = [r for r in inter['name'].names if r.platformID != 1]

    inter.save(output_path)
    size = os.path.getsize(output_path) / 1024 / 1024
    print(f"\nSaved: {output_path} ({size:.1f} MB)")
    print(f"  Glyphs: {len(glyph_order)}")
    print(f"  Axes: {[(a.axisTag, a.minValue, a.maxValue) for a in inter['fvar'].axes]}")


if __name__ == "__main__":
    inter_ttf = sys.argv[1]
    pretendard_ttf = sys.argv[2]
    output = sys.argv[3]
    merge(inter_ttf, pretendard_ttf, output)
