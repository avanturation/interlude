# Interlude 1.3의 소스와 배포

## 결정: Glyphs로 컴파일, Make로 검증·배포

편집 원본은 `src/Interlude.glyphspackage` 하나입니다. Glyphs 4.1.1 (4108)에서 Variable → TrueType → TTF와 WOFF2를 `fonts/`에 Export합니다. 플러그인이나 Export 후 테이블 보완은 필요하지 않습니다. `make`는 폰트 원본을 컴파일하지 않습니다.

검토한 upstream은 Inter 4.1과 Pretendard 1.3.9입니다.

| 프로젝트 | 참고한 구조 | Interlude에 적용한 판단 |
|---|---|---|
| [Inter 4.1](https://github.com/rsms/inter/blob/v4.1/Makefile) | Glyphs package → glyphspkg/fontmake → UFO/designspace → 가변·정적 폰트, Make로 배포 | 편집 소스와 배포 단계를 구분하는 구조를 따릅니다. 현재 소스의 Glyphs 전용 Variable GPOS, 앵커 컴파일, 컴포넌트 유지 설정은 Glyphs 출력으로 검증했으므로 fontmake를 동일한 컴파일러로 취급하지 않습니다. |
| [Pretendard 1.3.9](https://github.com/orioncactus/pretendard/tree/v1.3.9) | src의 Glyphs package, 패키지별 배포 파일, [서브셋 스크립트](https://github.com/orioncactus/pretendard/blob/v1.3.9/packages/pretendard-jp/package.json), [릴리스 패키징](https://github.com/orioncactus/pretendard/blob/v1.3.9/.github/workflows/release.yml) | 글꼴 제작과 웹 서브셋·npm·ZIP 배포를 분리합니다. Inter/Pretendard를 다시 내려받아 합치지 않습니다. |

별도의 fontmake 경로를 추가하면 같은 소스에 컴파일러가 둘 생겨 커닝·가변 델타·글리프 순서 차이까지 유지보수해야 합니다. 현재 요구인 Glyphs Export 결과를 기준으로 한 가지 컴파일 경로를 유지합니다. Glyphs가 없는 환경에서도 커밋된 `fonts/`를 검증하고 배포 파생물을 만들 수 있습니다.

## 작업 순서

가변 Export의 Family Name은 `Interlude Variable`, PostScript 이름은 `Interlude-Variable`입니다. 이 값은 Variable 인스턴스의 `properties`에 저장합니다. 구형 `familyName` 커스텀 파라미터는 현재 Glyphs에서 무시되므로 사용하지 않습니다. `make check`는 실제 TTF·WOFF2의 이름 테이블까지 검사합니다.

1. Glyphs에서 `src/Interlude.glyphspackage`를 열어 수정합니다.
2. File → Export → Variable → TrueType에서 `.ttf`와 `.woff2`를 선택하고 `fonts/`로 Export합니다.
3. `make record-export`로 버전·문자·기능 회귀 검사를 통과한 Export를 기록합니다.
4. `make test`, `make dist`, 필요하면 `make package`를 실행합니다.
5. 소스, `fonts/InterludeVariable.ttf`, `fonts/InterludeVariable.woff2`, `fonts/export-manifest.json`을 함께 커밋합니다.

`record-export`는 파일을 수정하거나 Glyphs를 자동 실행하지 않습니다. 새 Export의 출처를 사용자가 명시적으로 기록하는 단계이며, 해시만으로 어떤 앱이 컴파일했는지 증명하는 것은 아닙니다. `check`는 기록 이후 소스 또는 바이너리 변경을 감지합니다. 의도적으로 기능을 바꾼 경우에는 변경된 동작을 확인한 뒤 `tests/expected-font.json`의 해당 회귀 기준도 갱신합니다.

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
make check         # 커밋된 네이티브 출력과 소스가 대응하는지 확인
make test          # 검증 도구 테스트
make dist          # 웹 서브셋, 정적 웹폰트 18개, CSS, Next.js/npm 파일
make fonts         # Text/Display × 3폭 × 9굵기 = 54개 정적 TTF + TTC
make package       # 위 결과를 Interlude-1.3-ttf.zip, Interlude-1.3-web.zip으로 묶기
python3 tools/check_release.py  # 전체 package 결과의 내용 검사
npm pack           # prepack에서 make dist 실행; 게시하지 않음
```

기본 `make`는 도움말만 출력합니다. `make all`은 `make dist`와 같습니다. 폰트 자동 설치, 외부 다운로드, npm 게시, GitHub 릴리스 생성은 수행하지 않습니다. `make clean`은 `build/`, `dist/`, 이전 빌드의 Next.js 폰트 복사본만 지웁니다.

## 폴더

- `src/Interlude.glyphspackage/`: 12마스터, 윤곽·컴포넌트·앵커·OpenType 기능을 포함한 기준 소스.
- `src/provenance.json`: Inter 4.1, Pretendard JP 1.3.9, Interlude 1.2.4 기준 파일의 출처.
- `fonts/`: Glyphs가 직접 출력한 가변 TTF·WOFF2와 소스/출력 해시. 버전 관리 대상.
- `tools/`: 검증, 정적 인스턴스, 서브셋, 배포 패키징. 원본 윤곽을 바꾸는 빌더가 아님.
- `web/`: CSS와 고정된 Unicode 분할 계획. 빌드 중 Pretendard CSS를 받지 않음.
- `packages/next/`: 기존 `interlude-ui/font` import 경로를 위한 코드. 별도 npm 패키지/버전은 없음. `dist/woff2/InterludeVariable.woff2`를 공유해 같은 폰트를 중복 포함하지 않음.
- `tests/`: 54개 기능·혼합문자·가변 위치의 고정 회귀 기준과 도구 테스트.
- `docs/qa/`: 한글 균형, 속공간 보호, 한자 부품화, 커닝 검증의 근거.
- `build/`, `dist/`: 생성물. Git에 포함하지 않음.

정적 TTF와 서브셋은 네이티브 파일에서 파생하며, 가변 원본 파일을 덮어쓰지 않습니다. 웹 서브셋은 문자를 서로 다른 font-face로 나누므로 파일 경계를 넘는 문맥 치환이나 결합 부호 조합은 전체 WOFF2와 동작이 다를 수 있습니다. 혼합문자 OpenType 동작을 모두 우선할 때는 전체 Variable WOFF2를 사용하세요.

## 삭제·보존 판단

삭제한 것은 1.2의 Inter/Pretendard 바이너리 병합기, width 축 합성기, SF Pro 참조 계산 코드, 피처 주입기, 소스 안으로 흡수된 `.fea` 복사본, 비어 있던 submodule 설정입니다. 기존 Git 이력과 1.2 CHANGELOG는 남습니다. upstream의 원문 OFL 고지문도 `docs/licenses/`에 보존하고 배포물에 포함합니다. upstream의 별도 checkout은 레포 밖의 조사 자료이며 새 레포의 의존성이 아닙니다.

정적 인스턴스·서브셋·CSS·Next.js·Tailwind 제공 기능은 필요하므로 유지했습니다. 정적 폰트 생성 과정에서 별도 chws 삽입을 제거하고, 원본의 네이티브 GPOS를 그대로 인스턴싱합니다. 서브셋 오류는 더 이상 조용히 건너뛰지 않으며, 선언한 모든 Unicode가 출력에 있는지 검사합니다.

## 버전과 알려진 차이

공개 릴리스·태그·ZIP·CHANGELOG는 **1.3**입니다. `version.txt`도 `1.3`입니다. npm의 SemVer 필드만 `1.3.0`, Glyphs 및 OpenType의 숫자 표기는 `1.300`입니다. 두 표기는 동일한 1.3 릴리스를 뜻하며 패치 릴리스를 추가한 것이 아닙니다.

이전 네이티브 시험판에서 확인한 제한은 그대로입니다. Glyphs 4.1.1은 MVAR를 생성하지 않아 밑줄·취소선·x-height 메타데이터는 origin master 값입니다. 실제 윤곽의 축 변화는 유지됩니다. `bullet.case`의 이전 불연속 동작은 연속 보간으로 정리됐고 TrueType 반올림의 미세한 차이가 있습니다. 한자 부품화는 소스 좌표가 동일하지만 64px 래스터 비교의 정규화 절대 알파 차이 합은 최대 0.245%였습니다. 이전 바이너리와 바이트 또는 모든 픽셀이 동일하다는 의미는 아닙니다.

이전 레포에 커밋돼 있던 14,430,640-byte TTF는 opsz/wght 두 축만 있는 오래된 파일입니다. 아래 용량 비교 기준은 wdth를 포함한 최신 1.2.4 배포본이며, 오래된 체크인 파일과 직접 비교한 수치가 아닙니다.

1.3의 최적화된 TTF는 23,418,180 bytes로, 원본 배포본을 TTF로 푼 26,570,200 bytes보다 11.87% 작습니다. 한글 보정은 486개 축 위치에서 진단했고, 추가 최적화는 비대상 글리프 26,414개의 윤곽·가변 데이터를 유지한 채 커닝 중복과 한자 공통 윤곽을 정리했습니다.
