"""Inspect actual desktop/web deliverables after `make package`."""
from pathlib import Path
import hashlib,json,re,sys,zipfile
import uharfbuzz as hb
from fontTools.ttLib import TTFont,TTCollection
from source_state import ROOT,file_hash
from release import verify_subsets
from static_fonts import WEIGHTS,FAMILIES,WIDTHS
from check import check_variable_names

def shape(font,text):
    buf=hb.Buffer();buf.add_str(text);buf.guess_segment_properties();hb.shape(font,buf)
    return [(p.x_advance,p.y_advance,p.x_offset,p.y_offset)for p in buf.glyph_positions]
def main():
    source=TTFont(ROOT/'fonts/InterludeVariable.ttf');cmap=source.getBestCmap();face=hb.Face((ROOT/'fonts/InterludeVariable.ttf').read_bytes());vfont=hb.Font(face)
    check_variable_names(source)
    seen=set();compared=0;max_delta=0
    for opsz,prefix,family in FAMILIES:
        for width_name,width,width_class in WIDTHS:
            for style,weight in WEIGHTS:
                path=ROOT/'build/static'/f'{prefix}{width_name}-{style}.ttf';f=TTFont(path)
                assert not {'fvar','gvar','HVAR','MVAR'}&set(f.keys()),path.name
                assert f.getBestCmap()==cmap,path.name
                assert (f['OS/2'].usWeightClass,f['OS/2'].usWidthClass)==(weight,width_class)
                assert f['name'].getDebugName(5).startswith('Version 1.300')
                identity=(f['name'].getDebugName(1),f['name'].getDebugName(2));assert identity not in seen,identity;seen.add(identity)
                assert f['name'].getDebugName(3).startswith('1.3;')
                assert f['name'].getDebugName(16)==family
                assert f['name'].getDebugName(6)==f'{prefix}{width_name}-{style}'
                vfont.set_variations({'opsz':opsz,'wght':weight,'wdth':width});sfont=hb.Font(hb.Face(path.read_bytes()))
                for text in ['AVATAR To a\u0301 Ta\u0323Vo ffi ->','한글과 English 가@나 漢字 日本語','디지털 전환(DT) 한글(가나)']:
                    a,b=shape(vfont,text),shape(sfont,text);assert len(a)==len(b)
                    delta=max([abs(x-y)for aa,bb in zip(a,b)for x,y in zip(aa,bb)]+[0]);max_delta=max(max_delta,delta)
                    assert delta<=1,(path.name,text,delta)
                    compared+=1
    ttc=TTCollection(ROOT/'build/Interlude.ttc');assert len(ttc.fonts)==54
    for f in ttc.fonts:f.close()
    covered=verify_subsets(ROOT/'dist/dynamic-subset')
    for path in (ROOT/'dist/dynamic-subset').glob('*.woff2'):
        with TTFont(path) as font:check_variable_names(font)
    for css in (ROOT/'dist').rglob('*.css'):
        content=re.sub(r'/\*.*?\*/','',css.read_text(),flags=re.S)
        urls=re.findall(r"url\(['\"]?([^)'\"]+)",content)+re.findall(r'@import\s+"([^"]+)"',content)
        for url in urls:
            assert (css.parent/url).exists(),(str(css),url)
    assert file_hash(ROOT/'fonts/InterludeVariable.woff2')==file_hash(ROOT/'dist/woff2/InterludeVariable.woff2')
    for name in ['sans.mjs','display.mjs']:
        module=ROOT/'packages/next/dist'/name
        relative=re.search(r'src: "([^"]+)"',module.read_text())[1]
        assert (module.parent/relative).resolve()==(ROOT/'dist/woff2/InterludeVariable.woff2').resolve()
    for kind, member, source_path in [
        ('ttf', 'InterludeVariable.ttf', ROOT/'fonts/InterludeVariable.ttf'),
        ('web', 'woff2/InterludeVariable.woff2', ROOT/'fonts/InterludeVariable.woff2'),
    ]:
        with zipfile.ZipFile(ROOT/'build'/f'Interlude-1.3-{kind}.zip') as z:
            assert z.testzip() is None
            assert hashlib.sha256(z.read(member)).hexdigest() == file_hash(source_path), 'Stale variable font in ZIP'
    result={'release':'1.3','staticFonts':54,'staticShapingComparisons':compared,'maxStaticPositionRounding':max_delta,'unicodeSubsetCoverage':covered,'canonicalWOFF2CopiedUnchanged':True,'cssURLsExist':True}
    (ROOT/'build/validation-release.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
