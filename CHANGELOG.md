# 변경 이력

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
- Variable TTF: InterCJKVariable.ttf (단일 파일에 Text + Display)
- Static TTF: 9 weight × 2 패밀리 (Inter CJK + Inter CJK Display) = 18 파일
- TTC: InterCJK.ttc (18 static 합본)
- 웹: woff2 (variable + static) + dynamic subset (119분할)
- CSS: inter-cjk.css (Variable + Static + Display + @font-feature-values)
- npm: `inter-cjk` 패키지, jsDelivr CDN 지원
- Next.js: `inter-cjk/font` 패키지

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
- Variable TTF: InterCJKVariable.ttf
- Static TTF: 9 weight × 2 패밀리 = 18 파일
- 웹: woff2 (variable + static) + dynamic subset (119분할)
- CSS: inter-cjk.css + minified
- npm: `inter-cjk` 패키지, jsDelivr CDN 지원

### 빌드
- 소스: Inter (git submodule) + Pretendard JP (릴리즈 다운로드)
- 파이프라인: fontmake → merge → gen-static → woff2 → dynamic-subset
- 재현 가능: `make all`로 클린 빌드
