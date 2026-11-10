# Interlude 배포

Glyphs Export 후 일반판은 `make record-export`, 중국어는 `make record-chinese-export`로 검증 기록을 갱신합니다. 배포 버전은 `version.txt`와 `package.json`의 1.3.1, 폰트 내부 버전은 1.301입니다.

```sh
make test
make release
```

`build/release/1.3.1/`에 아래 파일이 준비됩니다. 이 명령은 외부에 게시하지 않습니다.

- 기존 구성: `Interlude-1.3.1-ttf.zip`, `Interlude-1.3.1-web.zip`, `InterludeVariable.ttf`
- 추가 파일: `InterludeVariable.woff2`, `Interlude-1.3.1-source.zip`
- 중국어: `Interlude-Chinese-1.3.1-fonts.zip`, `Interlude-Chinese-1.3.1-sources.zip`
- npm: `interlude-ui-1.3.1.tgz` — 일반판·CSS·Next.js·Tailwind·Dynamic Subset 구성 유지
- 검사 결과, `release-notes.md`, `SHA256SUMS`, 실제 게시 명령을 담은 `PUBLISH.md`

`make release`는 모든 소스·네이티브 출력과 정적·웹 결과를 검사한 다음 npm의 prepack 중복 실행 없이 패키지를 묶습니다. npm tarball 안의 실제 이름·버전·경로·라이선스도 확인합니다. 커밋된 폰트를 사용하므로 Glyphs가 없는 환경에서도 배포 파일을 준비할 수 있습니다.

GitHub에는 위 ZIP과 일반 Variable 파일을 릴리스 자산으로 올립니다. npm에는 준비된 tgz 자체를 게시합니다. `PUBLISH.md`의 명령은 릴리스 폴더에서 실행하며 GitHub 릴리스와 npm 게시를 각각 수행합니다. npm 인증은 계정의 패스키/브라우저 인증 절차를 따릅니다. `make release`는 태그·릴리스·npm 게시를 자동 실행하지 않습니다.

`SHA256SUMS`는 GitHub에 올리는 7개 폰트·ZIP 파일만 나열하므로 릴리스 자산을 내려받아 그대로 검사할 수 있습니다. npm tgz의 해시는 `validation-npm.json`과 `manifest.json`에 별도로 기록됩니다.
