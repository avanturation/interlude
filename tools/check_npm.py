"""Inspect the actual npm tarball without extracting or publishing it."""
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import posixpath
import re
import tarfile
from fontTools.ttLib import TTFont
from check import check_variable_names
from source_state import ROOT, file_hash
from versioning import RELEASE, FONT_REVISION, FONT_VERSION


def check_archive(path):
    expected=file_hash(ROOT/'fonts/InterludeVariable.woff2')
    with tarfile.open(path) as tar:
        files={m.name:m for m in tar.getmembers() if m.isfile()}
        def read(name):return tar.extractfile(files[name]).read()
        package=json.loads(read('package/package.json'))
        assert package['name']=='interlude-ui' and package['version']==RELEASE
        def targets(value):
            if isinstance(value,str):yield value
            elif isinstance(value,dict):
                for item in value.values():yield from targets(item)
            elif isinstance(value,list):
                for item in value:yield from targets(item)
        for target in targets(package['exports']):
            assert target.startswith('./') and 'package/'+target[2:] in files,target
        canonical=variable=fonts=0
        for name in files:
            if name.endswith('.woff2'):
                data=read(name);canonical+=hashlib.sha256(data).hexdigest()==expected
                with TTFont(BytesIO(data),lazy=True) as font:
                    assert abs(font['head'].fontRevision-FONT_REVISION)<.00002,name
                    assert font['name'].getDebugName(5).startswith(FONT_VERSION),name
                    if 'fvar' in font:
                        check_variable_names(font);variable+=1
                    fonts+=1
            if name.endswith('.css'):
                content=re.sub(r'/\*.*?\*/','',read(name).decode(),flags=re.S)
                urls=re.findall(r"url\(['\"]?([^)'\"]+)",content)+re.findall(r'@import\s+"([^"]+)"',content)
                for url in urls:
                    assert posixpath.normpath(posixpath.join(posixpath.dirname(name),url)) in files,(name,url)
        for name in ['sans.mjs','display.mjs']:
            name='package/packages/next/dist/'+name
            relative=re.search(r'src: "([^"]+)"',read(name).decode())[1]
            target=posixpath.normpath(posixpath.join(posixpath.dirname(name),relative))
            assert target=='package/dist/woff2/InterludeVariable.woff2' and target in files,target
        assert fonts==206 and variable==188 and canonical==1,(fonts,variable,canonical)
        for name in (ROOT/'docs/licenses').glob('*.txt'):
            assert read('package/dist/licenses/'+name.name)==name.read_bytes(),name.name
        assert read('package/LICENSE.txt')==(ROOT/'LICENSE.txt').read_bytes()
    data=Path(path).read_bytes()
    return {'release':RELEASE,'npmVersion':package['version'],'archive':Path(path).name,
            'bytes':len(data),'unpackedBytes':sum(m.size for m in files.values()),'files':len(files),
            'exportsResolved':True,'cssURLsResolved':True,'nextFontPathsResolved':True,
            'canonicalVariableWOFF2Copies':canonical,'variableFilesWithVerifiedNames':variable,
            'fontsWithVerifiedVersions':fonts,'originalLicensesIncluded':True,
            'sha256':hashlib.sha256(data).hexdigest(),'sha512':hashlib.sha512(data).hexdigest()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive');args=parser.parse_args()
    result=check_archive(Path(args.archive))
    (ROOT/'build/validation-npm.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
