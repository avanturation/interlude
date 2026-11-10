# Interlude Chinese 1.3.1

Source Han Sans 2.005를 바탕으로 만든 중국어 전용 가변 폰트입니다. 일반판에는 중국어 전용 확장 데이터를 추가하지 않았습니다. 일반판의 기존 한·일용 한자는 유지하므로 중국어와 공유하는 한자도 일부 표시됩니다.

| 지역 | 메뉴 이름 | 한자 코드포인트 | TTF | WOFF2 |
| --- | --- | ---: | ---: | ---: |
| 간체 | Interlude SC Variable | 27,923 | 57.48 MB | 30.87 MB |
| 대만 번체 | Interlude TC Variable | 17,760 | 38.25 MB | 20.48 MB |
| 홍콩 번체 | Interlude HK Variable | 17,769 | 38.17 MB | 20.55 MB |

한자 수에는 호환 한자가 포함됩니다. 각 파일은 영문·그리스·키릴 문자와 해당 지역의 중국어를 포함하며 한글·가나는 포함하지 않습니다. Weight 100–900(기본 400), Width 75–125(기본 100), Optical Size 14–32(기본 14)를 지원합니다. 배포 버전은 1.3.1, 폰트 내부 버전은 1.301입니다.

## 사용

저장소의 `fonts/InterludeSCVariable.ttf`, `InterludeTCVariable.ttf`, `InterludeHKVariable.ttf` 중 필요한 지역을 설치합니다. 폰트 배포 ZIP에서는 `desktop/`에 있습니다. 웹에서는 각 WOFF2와 `web/interlude-chinese.css`를 함께 사용합니다. 저장소에서는 CSS의 상대 경로에 맞춰 필요한 WOFF2를 같은 웹 폴더에 복사합니다.

```css
html[lang="zh-CN"] { font-family: "Interlude SC Variable", "Interlude Variable", sans-serif; }
html[lang="zh-TW"] { font-family: "Interlude TC Variable", "Interlude Variable", sans-serif; }
html[lang="zh-HK"] { font-family: "Interlude HK Variable", "Interlude Variable", sans-serif; }
```

기존 `interlude-ui` npm 패키지는 일반판과 기존 import 경로를 유지합니다. 중국어 파일은 별도 ZIP으로 제공하므로 일반판 npm 용량에 더해지지 않습니다.

## 편집과 Export

저장소의 `src/InterludeSC.glyphspackage`, `InterludeTC.glyphspackage`, `InterludeHK.glyphspackage`를 Glyphs 4에서 각각 엽니다. 별도 중국어 소스 ZIP에서는 `sources/`에 있습니다. 패키지마다 윤곽·앵커·기능·12개 마스터가 모두 들어 있습니다.

File → Export → Variable → TrueType에서 TTF와 WOFF2를 선택해 `fonts/`에 출력합니다. 원본 Inter/Pretendard/Source Han Sans 파일, 보완 플러그인, 바이너리 후처리는 필요하지 않습니다. 수정 후 `make record-chinese-export`, `make test`, `make package-chinese`로 확인하고 소스·폰트·`fonts/chinese-export-manifest.json`을 함께 커밋합니다.

## 형태와 검증

영문은 기존 Interlude의 윤곽·마스터·커닝을 유지합니다. 중국어는 지역별 자형을 보존하고 전각 자폭을 1920/2048 em으로 줄였으며 세로 비율과 기준선을 맞췄습니다. Display에서는 몸체 폭을 추가로 2% 줄였습니다. 중국어의 100·400·900 마스터는 Source Han Sans의 250·400·900에 대응하며 중간 굵기는 Interlude의 축 매핑으로 보간합니다.

숫자 콜론의 기본 중앙 정렬, 폭에 따라 변하는 연속 문장부호 보정, 세로쓰기, 중국어 문맥의 주음 성조를 포함합니다. 영문 악센트는 중국어 성조와 다른 윤곽을 사용합니다.

`make check-chinese`는 소스·출력 해시와 버전·이름·축, 중복 Unicode와 중국어 마스터 호환성, 한글·가나 혼입을 검사합니다. 지역마다 영문 조판 436건, 대표 중국어 마스터 윤곽 SC 540건 / TC·HK 480건, 숫자 콜론 216건, 전각 폭·문장부호 보정·세로 기준점 각각 54건, 주음 성조 864건을 검사하고 TTF·WOFF2의 가변·레이아웃 테이블을 비교합니다.

실제 출력으로 만든 미리보기는 `docs/qa/chinese/proof-weights.png`, `proof-axes.png`, `proof-bopomofo.png`에 있습니다. HarfBuzz·FreeType 검사이며 Figma 자체의 UI 검사를 뜻하지는 않습니다.

## 출처

Apple 폰트는 사용하지 않았습니다. Source Han Sans의 고정 커밋·원본 URL·SHA-256·변형 값은 `src/chinese-provenance.json`, OFL 고지는 `docs/licenses/SourceHanSans-OFL.txt`에 있습니다. 배포 ZIP에도 Interlude·Inter·Pretendard·Source Han Sans의 고지를 포함합니다.
