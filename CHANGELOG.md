# 변경 이력

## 1.2.0 (2026-06-07)

가변 폭(wdth) 축 추가 + Latin/CJK 굵기 밸런스 정교화.

### wdth 축
- **wdth 축 신규 추가 (75–150)**: Condensed부터 Expanded까지 가변 폭 지원
  - dual expansion master (125 / 150)로 전 구간 0.00u fidelity
  - 대각선 글자 직선성 보정 (Y/X/V/W/A/v/z), k/K weld min-overlap clamp
  - Condensed-Black 카운터 막힘 보정: wght×wdth 교차 gvar 튜플 (18,406 글자)
- named instances 27개 (Condensed/Normal/Expanded × 9 weights)
- STAT 테이블 width 축 4단계 (Condensed/Normal/Expanded/Extra Expanded)

### 굵기 밸런스
- CJK weight 매핑: BOLD_SCALE/THIN_SCALE 1.0 (Pretendard native deltas, 전 구간 회색도 평탄화)
- Latin straight-stem(H/l/I/n) 균일 thinning (corner correction 전체 알파벳 확장)
- Latin Medium~Black avar evenness: 끝점 고정, 500–800 재분배 (+38.5 plateau → +42/43 균일)
- Latin heavy 미세 thinning: wght 400 고정, 900으로 갈수록 -3% 점진 (peak 델타 0.944배)

### 웹/패키지
- CSS/Next.js wdth 지원: `@font-face`에 `font-stretch: 75% 150%`
  - misc/interlude.css, gen-dynamic-subset.py
  - packages/next sans/display.mjs: declarations로 font-stretch 주입

### 빌드
- Makefile: OS 자동 감지 폰트 설치 타겟 (macOS/Windows/Linux), `make all`에 연결
- check-font: wdth 75–150 범위 검증 추가
- gen-static: 정적 폰트 생성 시 wdth=100 핀

## 1.1.0 (2025-06-04)

리브랜딩 + CJK 밸런스 보정.

### 브랜딩
- Inter CJK → **Interlude**로 폰트명 전면 변경
- vendorID: ICJK → INTL
- name table 전면 정비 (stale InterVariable-* 레코드 제거, nameID 3/25 설정, instance postScriptNameID 할당)
- npm 패키지: `inter-cjk` → `interlude`

### CJK 밸런스
- CJK 수직 스케일 1.029 적용 (Inter capHeight 1490 / Pretendard capHeight 1448 비율 보정)
- CJK weight 매핑: 우리 wght=400에서 Pretendard wght=430 두께 사용 (한영 회색도 균형)
- CJK_HSCALE 1.0으로 변경 (수평 축소 제거)
- Y_OFFSET 0으로 변경 (수직 스케일이 자연 정렬 처리)

### 버그 수정
- Static 폰트 fsSelection/macStyle BOLD 비트 정상 설정
- nameID 16/17 (Typographic Family/Subfamily) 추가
- OTF 가짜 파일 제거 (CFF 없는 .otf 출력 중단)
- Pretendard submodule 제거, CSS를 GitHub raw에서 다운로드
- usWinAscent/Descent를 글리프 bbox 커버하도록 수정 (Windows 클리핑 방지)
- STAT 테이블: ital 축 제거, Display opsz=32 elidable 해제
- Latin-CJK kern dead code 제거 (LATIN_CJK_SPACING=0 no-op)
- ₩ 글리프에 CJK 보정 (Y_OFFSET, HSCALE, VSCALE) 적용
- chws를 static 폰트에도 적용
- bare except → except Exception 변환
- unicode-range ? 와일드카드 파싱 지원
- gen-css.py 죽은 코드 삭제
- ZIP 패키징에 -X 플래그 추가 (macOS 잡파일 제거)
- PRETENDARD_CSS를 Makefile dependency에 추가

### 빌드
- Inter/Pretendard 모두 릴리즈 바이너리 다운로드 (submodule 완전 제거)
- `git clone` 한 방으로 빌드 가능 (submodule 불필요)

## 1.0.0 (2025-05-31)

정식 릴리즈.

### 폰트
- Inter 4.1 + Pretendard JP 1.3.9 기반 Variable 폰트 1개 (opsz 14–32, wght 100–900)
- 22,981 글리프, 22,241 코드포인트
- CJK 수직 정렬: Y offset +21
- CJK 회색도 매칭: 수평 1% 축소
- CJK 광학 크기: opsz=32(Display)에서 3% 축소
- ₩ (원화 기호) Pretendard JP 한국식 글리프로 교체
- Vertical Metrics: SUIT 비율 (asc=2024, desc=-532, ratio=1.248)
- 16px → 20, 18px → 22 짝수 Line Height

### OpenType (53개)
- Inter의 모든 피처 유지 (calt, ccmp, case, dlig, frac, tnum, zero, cv01-14, ss01-04, ss07-08)
- `rlig` 추가: CJK 컨텍스트 기호 자동 정렬 (49개 기호 `.case` 치환, Hangul shaper 호환)
- `ss05` Korean Localization: 한글 컨텍스트 줄임표 `.hang` + 한자 지역화 522쌍
- `ss06` Pretendard Disambiguation: I, l, 1 구분 강화
- `ss09` Circled and Squared Characters: 원문자·괄호문자 변환
- `ss10–ss16` Pretendard 심벌 세트 (Medium, Outlined, Circled, Squared, Filled, Small, Large)
- `chws`/`halt` CJK 구두점 반각 자동 조절 (east_asian_spacing)
- GSUB/GPOS에 CJK 스크립트 등록 (kana, hani)

### 배포
- Variable TTF: InterludeVariable.ttf (단일 파일에 Text + Display)
- Static TTF: 9 weight × 2 패밀리 (Interlude + Interlude Display) = 18 파일
- TTC: Interlude.ttc (18 static 합본)
- 웹: woff2 (variable + static) + dynamic subset (119분할)
- CSS: interlude.css (Variable + Static + Display + @font-feature-values)
- npm: `interlude` 패키지, jsDelivr CDN 지원
- Next.js: `interlude/font` 패키지

### 빌드
- 소스: Inter 4.1 릴리즈 TTF + Pretendard JP 1.3.9 릴리즈 TTF (자동 다운로드)
- Pretendard submodule은 dynamic-subset CSS 참조용으로만 유지
- 파이프라인: `make all` (다운로드 → merge → chws → static → woff2 → dynamic-subset)
- QA: `make check` (metrics, line height, calt, ss05, weight variation, opsz, glyph count, OpenType 작동 검증)

### 0.1.0 이후 변경사항
- Vertical Metrics를 SUIT 비율로 변경 (asc=1897→2024, desc=-407→-532)
- `rclt` → `calt`+`rlig`로 이전 (피그마 호환성)
- `hang` 스크립트 제거 (Pretendard 방식, harfbuzz Hangul shaper 호환)
- Inter submodule 제거, 릴리즈 바이너리 다운로드로 전환
- Composite glyph 보존 (i, j, Adieresis 등 gvar 유실 수정)
- ss05/ss06 이름 수정 (Korean Localization, Pretendard Disambiguation)
- fontbakery: FAIL 2 (구조적), WARN 6 (구조적), PASS 97

---

## 0.1.0 (2025-05-24)

최초 프리릴리즈.

### 폰트
- Inter Variable (opsz + wght)과 Pretendard JP Variable (wght) 합침
- CJK 수직 정렬: Y offset +21
- CJK 회색도 매칭: 수평 1% 축소
- CJK 광학 크기: opsz=32(Display)에서 3% 축소
- ₩ (원화 기호)를 Pretendard JP의 한국식 글리프로 교체
- `rclt` 피처: CJK 인접 시 49개 기호가 자동으로 .case 버전으로 치환
- Vertical Metrics: ratio 1.125, cap center 기준 대칭 (asc=1897, desc=-407)
- 피그마에서 12/14/16/18px Line Height 짝수

### OpenType
- Inter의 모든 피처 유지 (calt, ccmp, case, dlig, frac, tnum, zero, cv01-16, ss01-08)
- `rclt` 추가: CJK 컨텍스트 기호 정렬
- GSUB/GPOS에 CJK 스크립트 등록 (hang, kana, hani)

### 배포
- Variable TTF: InterludeVariable.ttf
- Static TTF: 9 weight × 2 패밀리 = 18 파일
- 웹: woff2 (variable + static) + dynamic subset (119분할)
- CSS: interlude.css + minified
- npm: `interlude` 패키지, jsDelivr CDN 지원

### 빌드
- 소스: Inter (git submodule) + Pretendard JP (릴리즈 다운로드)
- 파이프라인: fontmake → merge → gen-static → woff2 → dynamic-subset
- 재현 가능: `make all`로 클린 빌드
