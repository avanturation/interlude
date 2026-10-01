"""Package native Glyphs exports; never compile or patch the source font."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, subprocess, sys, zipfile
from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection
from source_state import ROOT, file_hash
from subset_fonts import generate, parse_unicode_ranges, unicode_range_to_codepoints
BUILD=ROOT/'build'; DIST=ROOT/'dist'; FONT=ROOT/'fonts/InterludeVariable.ttf'

def run(*args):subprocess.run([sys.executable,*map(str,args)],check=True,cwd=ROOT)
def cache_key(*paths):
    h=hashlib.sha256()
    for p in paths:h.update(Path(p).read_bytes())
    return h.hexdigest()
def verify_subsets(folder):
    css=(folder/'interlude-variable-dynamic-subset.css').read_text();covered=set();source=set(TTFont(FONT).getBestCmap())
    for block in re.findall(r'@font-face\s*\{(.*?)\}',css,re.S):
        name=re.search(r"url\('./([^']+)'\)",block)[1]
        declared=unicode_range_to_codepoints(re.search(r'unicode-range:\s*([^;]+)',block)[1])
        actual=set(TTFont(folder/name).getBestCmap())
        assert declared<=actual,(name,'CSS declares missing characters')
        assert not covered&declared,(name,'Overlapping Unicode partition')
        covered.update(declared)
    assert covered==source, f'Missing subset coverage: {len(source-covered)}'
    return len(covered)
def web():
    out=BUILD/'web';out.mkdir(parents=True,exist_ok=True)
    for name in ['woff2','css','dynamic-subset','tailwind']:(out/name).mkdir(exist_ok=True)
    run(ROOT/'tools/static_fonts.py',FONT,BUILD/'static','--web-only')
    # The canonical variable WOFF2 is copied byte-for-byte from Glyphs.
    shutil.copy2(ROOT/'fonts/InterludeVariable.woff2',out/'woff2/InterludeVariable.woff2')
    for path in sorted((BUILD/'static').glob('*.ttf')):
        if 'Condensed' in path.name or 'Expanded' in path.name:continue
        target=out/'woff2'/(path.stem+'.woff2')
        if not target.exists()or target.stat().st_mtime<path.stat().st_mtime:
            font=TTFont(path);font.flavor='woff2';font.save(target)
    shutil.copy2(ROOT/'web/interlude.css',out/'css/interlude.css')
    css=(out/'css/interlude.css').read_text();css=re.sub(r'/\*.*?\*/','',css,flags=re.S);css=re.sub(r'\s+',' ',css).strip()
    (out/'css/interlude.min.css').write_text(css+'\n')
    shutil.copy2(ROOT/'web/interlude-tailwind.css',out/'tailwind/interlude.css')
    folder=out/'dynamic-subset';marker=folder/'.input-sha256';key=cache_key(FONT,ROOT/'tools/subset_fonts.py',ROOT/'web/subsets.json')
    if not marker.exists()or marker.read_text()!=key:
        shutil.rmtree(folder);folder.mkdir()
        generate(str(FONT),str(ROOT/'web/subsets.json'),str(folder),'Interlude Variable','interlude-variable-dynamic-subset.css')
        verify_subsets(folder);marker.write_text(key)
    print('Web files ready; Unicode coverage:',verify_subsets(folder),flush=True)
def dist():
    if DIST.exists():shutil.rmtree(DIST)
    shutil.copytree(BUILD/'web',DIST,ignore=shutil.ignore_patterns('.input-sha256'))
    shutil.copytree(ROOT/'docs/licenses',DIST/'licenses')
    (DIST/'variable').mkdir();shutil.copy2(FONT,DIST/'variable/InterludeVariable.ttf');shutil.copy2(ROOT/'LICENSE.txt',DIST/'LICENSE.txt')
    legacy=ROOT/'packages/next/dist/fonts'
    if legacy.exists():shutil.rmtree(legacy)
    # Next.js wrappers reference this same canonical distribution WOFF2.
    assert file_hash(DIST/'woff2/InterludeVariable.woff2')==file_hash(ROOT/'fonts/InterludeVariable.woff2')
    print('npm distribution ready',flush=True)
def ttc():
    paths=sorted((BUILD/'static').glob('*.ttf'));assert len(paths)==54
    col=TTCollection();col.fonts=[TTFont(p)for p in paths];col.save(BUILD/'Interlude.ttc')
    for f in col.fonts:f.close()
    print('TTC ready: 54 styles',flush=True)
def package():
    version=(ROOT/'version.txt').read_text().strip()
    with zipfile.ZipFile(BUILD/f'Interlude-{version}-ttf.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
        z.write(FONT,'InterludeVariable.ttf');z.write(BUILD/'Interlude.ttc','Interlude.ttc');z.write(ROOT/'LICENSE.txt','LICENSE.txt')
        for p in sorted((BUILD/'static').glob('*.ttf')):z.write(p,'ttf/'+p.name)
        for p in sorted((ROOT/'docs/licenses').glob('*.txt')):z.write(p,'licenses/'+p.name)
    with zipfile.ZipFile(BUILD/f'Interlude-{version}-web.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
        for p in sorted(DIST.rglob('*')):
            if p.is_file()and 'variable' not in p.relative_to(DIST).parts:z.write(p,p.relative_to(DIST))
    for p in BUILD.glob(f'Interlude-{version}-*.zip'):
        with zipfile.ZipFile(p)as z:assert z.testzip()is None
        print(p.name,p.stat().st_size,flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['web','dist','ttc','package']);args=parser.parse_args();globals()[args.command]()
