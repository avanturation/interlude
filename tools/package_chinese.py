"""Package native regional exports and independent Glyphs sources."""
from pathlib import Path
import json
import zipfile
from source_state import ROOT, file_hash, source_hash
from versioning import RELEASE

REGIONS=['SC','TC','HK']


def main():
    build=ROOT/'build';build.mkdir(exist_ok=True)
    manifest=ROOT/'fonts/chinese-export-manifest.json'
    saved=json.loads(manifest.read_text())
    assert saved['release']==RELEASE
    for r in REGIONS:
        report=saved['regions'][r]
        package=ROOT/'src'/f'Interlude{r}.glyphspackage'
        assert source_hash(package)==report['sourceSHA256'],r
        assert file_hash(ROOT/'fonts/InterludeVariable.ttf')==report['baselineSHA256'],r
        for name,expected in report['files'].items():
            assert file_hash(ROOT/'fonts'/name)==expected['sha256'],name
    common=[(ROOT/'docs/CHINESE.md','README.md'),
            (ROOT/'CHANGELOG.md','CHANGELOG.md'),
            (ROOT/'src/chinese-provenance.json','provenance.json'),
            (manifest,'manifest.json'),
            (ROOT/'LICENSE.txt','licenses/Interlude-OFL.txt')]
    common += [(p,'licenses/'+p.name) for p in sorted((ROOT/'docs/licenses').glob('*.txt'))]
    target=build/f'Interlude-Chinese-{RELEASE}-fonts.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for r in REGIONS:
            for ext,folder in [('ttf','desktop'),('woff2','web')]:
                p=ROOT/'fonts'/f'Interlude{r}Variable.{ext}'
                z.write(p,folder+'/'+p.name)
        z.write(ROOT/'web/interlude-chinese.css','web/interlude-chinese.css')
        for p in sorted((ROOT/'docs/qa/chinese').glob('*')):
            if p.is_file():z.write(p,'qa/'+p.name)
        for p,name in common:z.write(p,name)
    print(target.name,target.stat().st_size,flush=True)
    target=build/f'Interlude-Chinese-{RELEASE}-sources.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for r in REGIONS:
            package=ROOT/'src'/f'Interlude{r}.glyphspackage'
            for p in sorted(package.rglob('*')):
                if p.is_file() and p.suffix in ('.glyph','.plist') and p.name!='UIState.plist':
                    z.write(p,Path('sources')/package.name/p.relative_to(package))
        for p,name in common:z.write(p,name)
    print(target.name,target.stat().st_size,flush=True)


if __name__=='__main__':main()
