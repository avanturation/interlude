"""Prepare verified release assets and publication instructions; never publish."""
from pathlib import Path
import argparse
import json
import shlex
import shutil
import subprocess
import zipfile
from check_npm import check_archive
from source_state import ROOT, file_hash
from versioning import RELEASE, FONT_REVISION


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'build/release'/RELEASE)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    names=[f'Interlude-{RELEASE}-ttf.zip',f'Interlude-{RELEASE}-web.zip',
           f'Interlude-{RELEASE}-source.zip',f'Interlude-Chinese-{RELEASE}-fonts.zip',
           f'Interlude-Chinese-{RELEASE}-sources.zip']
    for name in names:
        path=ROOT/'build'/name
        with zipfile.ZipFile(path) as z:assert z.testzip() is None,name
        shutil.copy2(path,out/name)
    for name in ['InterludeVariable.ttf','InterludeVariable.woff2']:
        shutil.copy2(ROOT/'fonts'/name,out/name);names.append(name)
    for name in ['export-manifest.json','chinese-export-manifest.json']:
        shutil.copy2(ROOT/'fonts'/name,out/name)
    shutil.copy2(ROOT/'build/validation-release.json',out/'validation-release.json')
    cmd=['npm','--cache',str(ROOT/'build/npm-cache'),'pack','--ignore-scripts','--json','--pack-destination',str(out)]
    packed=subprocess.run(cmd,cwd=ROOT,check=True,capture_output=True,text=True)
    result=json.loads(packed.stdout);assert len(result)==1,result
    npm=out/result[0]['filename'];assert npm.name==f'interlude-ui-{RELEASE}.tgz'
    validation=check_archive(npm)
    for target in [out/'validation-npm.json',ROOT/'build/validation-npm.json']:
        target.write_text(json.dumps(validation,indent=2)+'\n')
    names.append(npm.name)
    changelog=(ROOT/'CHANGELOG.md').read_text()
    section=changelog.split('## '+RELEASE+' ',1)[1].split('\n## ',1)[0]
    notes='# Interlude '+RELEASE+' '+section+'\n\n'
    notes+='일반판은 한·일용 한자를 유지합니다. 중국어와 공유하는 한자도 일부 표시되며, 중국어 전용 확장 데이터는 SC·TC·HK 파일로 분리합니다.\n\n'
    notes+=f'일반판 이름: Interlude / Interlude Display / Interlude Variable. 폰트 내부 버전은 {FONT_REVISION:.3f}입니다.\n'
    (out/'release-notes.md').write_text(notes)
    github=['gh','release','create',RELEASE,'--repo','avanturation/interlude','--target','main','--title',RELEASE,'--notes-file','release-notes.md']+names[:-1]+['SHA256SUMS']
    publish='# 게시 명령\n\n이 폴더에서 실행합니다. 파일 준비 단계에서는 실행하지 않았습니다.\n\n```sh\n'+shlex.join(github)+'\n\n'+shlex.join(['npm','publish',npm.name,'--access','public'])+'\n```\n\nnpm은 계정의 패스키/브라우저 인증 절차를 따릅니다.\n'
    (out/'PUBLISH.md').write_text(publish)
    manifest={'release':RELEASE,'fontRevision':f'{FONT_REVISION:.3f}','githubReleasePublished':False,'npmPublished':False,
              'assets':{name:{'bytes':(out/name).stat().st_size,'sha256':file_hash(out/name)} for name in names}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    rows=['# Interlude '+RELEASE+' 배포 파일','',
          '일반판·중국어 SC/TC/HK의 소스, 폰트, npm 패키지입니다. 모든 파일은 검증을 마쳤으며 외부 게시 전입니다.','',
          '| 파일 | 크기 |','| --- | ---: |']
    for name in names:rows.append(f'| [{name}]({name}) | {(out/name).stat().st_size/1000000:.2f} MB |')
    rows+=['','[릴리스 노트](release-notes.md) · [실제 게시 명령](PUBLISH.md) · [SHA-256](SHA256SUMS)','']
    (out/'README.md').write_text('\n'.join(rows))
    # Match the files uploaded by the GitHub command; npm has its own report.
    sums=[file_hash(out/name)+'  '+name for name in sorted(names[:-1])]
    (out/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print('Prepared release:',out,flush=True)
    print('Verified npm:',validation['fontsWithVerifiedVersions'],'fonts;',validation['bytes'],'bytes',flush=True)


if __name__=='__main__':main()
