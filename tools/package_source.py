"""Package the standalone editable general Glyphs source."""
from pathlib import Path
import zipfile
from versioning import ROOT,RELEASE

def main():
    build=ROOT/'build';build.mkdir(exist_ok=True)
    package=ROOT/'src/Interlude.glyphspackage'
    target=build/('Interlude-'+RELEASE+'-source.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(package.rglob('*')):
            if p.is_file() and p.suffix in ['.glyph','.plist'] and p.name!='UIState.plist':z.write(p,Path(package.name)/p.relative_to(package))
        z.write(ROOT/'LICENSE.txt','LICENSE.txt')
        z.write(ROOT/'docs/BUILD.md','BUILD.md');z.write(ROOT/'CHANGELOG.md','CHANGELOG.md')
        for p in sorted((ROOT/'docs/licenses').glob('*.txt')):z.write(p,Path('licenses')/p.name)
    print(target.name,target.stat().st_size,flush=True)
if __name__=='__main__':main()
