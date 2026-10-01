"""Validate native exports, feature behavior, and source/export correspondence."""
from pathlib import Path
import argparse, json, math
import openstep_plist
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from source_state import ROOT, SOURCE, source_hash, file_hash

def check_fonts():
    version = (ROOT/'version.txt').read_text().strip()
    assert version == '1.3', 'This release is 1.3'
    package = json.loads((ROOT/'package.json').read_text())
    assert package['version'] == '1.3.0', 'npm uses the SemVer spelling of 1.3'
    info = openstep_plist.loads((SOURCE/'fontinfo.plist').read_text(), use_numbers=True)
    assert (info['versionMajor'], info['versionMinor']) == (1, 300)
    assert len(info['fontMaster']) == 12
    assert not info.get('userData', {}).get('com.interlude.completeExport')
    paths = [ROOT/'fonts'/('InterludeVariable.'+ext) for ext in ('ttf', 'woff2')]
    fonts = [TTFont(p) for p in paths]
    expected_axes = [('opsz',14,14,32), ('wght',100,400,900), ('wdth',75,100,125)]
    baseline = json.loads((ROOT/'tests/expected-font.json').read_text())
    for f in fonts:
        assert [(a.axisTag,a.minValue,a.defaultValue,a.maxValue) for a in f['fvar'].axes] == expected_axes
        assert abs(f['head'].fontRevision - 1.3) < .00002
        assert f['name'].getDebugName(5).startswith('Version 1.300')
        assert len(f.getBestCmap()) == 22241
        assert len(f.getGlyphOrder()) == 30427
        assert set(range(0xAC00,0xD7A4)) <= f.getBestCmap().keys()
        tags = sorted({r.FeatureTag for table in ('GSUB','GPOS') for r in f[table].table.FeatureList.FeatureRecord})
        assert tags == baseline['features'], 'Missing or changed OpenType feature tags'
        assert (f['OS/2'].sTypoAscender, f['OS/2'].sTypoDescender, f['hhea'].ascent,f['hhea'].descent)==(2024,-532,2024,-532)
    assert fonts[0].getBestCmap() == fonts[1].getBestCmap()
    for tag in ('GSUB','GPOS','GDEF','gvar','fvar'):
        assert fonts[0].getTableData(tag) == fonts[1].getTableData(tag), tag
    face = hb.Face(paths[0].read_bytes()); font = hb.Font(face)
    def shape(text, loc, features, language):
        font.set_variations(loc); buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties(); buf.language=language
        hb.shape(font,buf,features)
        order=fonts[0].getGlyphOrder()
        return [[order[i.codepoint],i.cluster,p.x_advance,p.y_advance,p.x_offset,p.y_offset] for i,p in zip(buf.glyph_infos,buf.glyph_positions)]
    for case in baseline['shaping']:
        got=shape(case['text'],case['location'],case['features'],case['language'])
        assert got==case['result'], (case['text'],case['location'],case['features'])
    return {'release':version,'compiler':'Glyphs 4.1.1 (4108), native Variable TrueType export','sourceSHA256':source_hash(),'files':{str(p.relative_to(ROOT)):file_hash(p) for p in paths},'shapingCases':len(baseline['shaping'])}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',action='store_true',help='Record a fresh, explicitly completed Glyphs export after validation')
    args=parser.parse_args();actual=check_fonts();path=ROOT/'fonts/export-manifest.json'
    if args.record:
        path.write_text(json.dumps(actual,indent=2)+'\n');print('Recorded native export manifest')
    else:
        saved=json.loads(path.read_text())
        assert actual==saved, 'Source/export mismatch. Export both fonts in Glyphs, then run make record-export.'
        print('Native source, version 1.3, TTF/WOFF2, 54 features and shaping regression checks passed.')
if __name__=='__main__': main()
