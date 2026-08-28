# 변경 이력

## 1.2.3 (2026-08-27)

Display 크기 CJK 왜곡 개선, 원문자·사각문자 크기 정상화.

### Display CJK 압축 분리

- **opsz 압축을 획(outline)과 자폭(advance)으로 분리**: 기존에는 `OPSZ_SCALE` 하나로 둘을 함께 3% 줄여, 자간이 좁아지는 동시에 글자 모양까지 납작해졌음
- `OPSZ_OUTLINE_SCALE` 2%, `OPSZ_ADVANCE_SCALE` 3%로 분리 — 자간 압축(밀도감)은 유지하고 획 압축(왜곡)만 1/3로 감소
- 가로로만 줄이면 세로획은 얇아지고 가로획은 두께가 남아 CJK 획 대비가 뒤집히는데, 이것이 40px 이상에서 "찌부" 현상으로 나타나던 원인
- Display에서 가 획 변화 −2.99% → −1.98%, 자폭은 −2.99% 유지
- 라틴은 Inter 원본 동작 유지 (H 획 −0.69% / 자폭 −4.73%)
- wdth 축 무영향 확인: opsz=14에서 세 폭 모두 변경 전과 동일, 압축비 75%/100%/125% 유지

### 기호 크기 정상화

- **원문자·사각문자 63자를 Pretendard 소스로 교체**: Inter의 해당 글리프는 디스플레이 스펙(① 2798×2798)으로 그려져 한글 옆에서 1.53배 크게 보이고 em box(2024/−532)를 벗어났음
- ① 높이 2798 → 1626 (가 대비 1.53배 → 0.89배), 🄰 1.88배 → 0.80배
- 글리프를 공유하는 Dingbat 원숫자(U+2780–2788) 9자도 함께 정상화되어 실질 72자 적용
- 대상 범위: U+2117, U+2460–24FF, U+3200–32FF, U+3300–33FF, U+1F100–1F1AC
- Inter가 Pretendard보다 1.25배 이상 큰 경우에만 교체하여, 향후 Inter 개선 시 자동으로 적용 제외
- `.medium` 변형 대신 소스 교체를 택한 이유: `.medium`은 wdth·opsz 델타가 없어 Condensed에서 폭이 고정됨
- GSUB 무손상 — ss09/ss10/ss13/ss14/ss02 동작 및 글리프 ID 교체 전후 동일
- ₩ 회귀 없음

## 1.2.2 (2026-07-07)

Dynamic Subset에서 한글 음절 누락 수정.

### 버그 수정

- **Dynamic Subset 한글 음절 누락**: `unicode-range`에 한글 음절 블록(U+AC00–D7A3, 11,172자)이 선언되지 않아 브라우저가 해당 subset을 로드하지 않던 문제 수정
- 원인: reference CSS로 Pretendard **JP**(일본어 전용)를 사용하여 한글 범위가 빠져 있었음
- `gen-dynamic-subset.py`가 reference CSS에 없지만 폰트에 포함된 코드포인트를 자동으로 추가 subset으로 생성하도록 변경

## 1.2.1 (2026-06-15)

wdth 축 획 균일성 근본 수정.

### wdth 축 개선

- **글리프 클래스 기반 압축 시스템**: narrow / diagonal / diag_multi / multi_stem / default 5개 클래스별 차별화된 stem_preserve, sb_damp 적용
- 글리프 간 width ratio spread 0.235 → 0.056 (76% 감소)
- Single-stem 글리프(I, l, i, j) 과도한 폭 유지 문제 해결 (0.98 → 0.75)
- Multi-stem 글리프(h, n, u, H, E, F) 압축 부족 문제 해결 (0.81 → 0.79)
- N/M/W diag_multi 클래스 분리: stem이 많은 대각선 글리프의 별도 압축 전략
- Tangent repair를 projection 방식으로 교체: off-curve 회전 대신 법선 성분 제거로 곡선 형태 보존
- 양방향 tangent repair (line→curve + curve→line junction)
- Diagonal preservation + tangent repair를 whitelist 글리프에만 적용 (i/j/구두점 부작용 제거)
- `_build_monotone_warp`에 stem_preserve 파라미터화: 클래스별 동적 stem 보존률

### 글리프 조정

- Bullet (U+2022) 크기를 SF Pro/Pretendard 수준으로 축소 (640→400, scale 0.625)

## 1.2.0 (2026-06-14)

가변 폭(wdth) 축 추가.

### wdth 축

- **wdth 축 신규 추가 (75–125)**: Condensed부터 Expanded까지 가변 폭 지원
- Monotone cosine-eased warp 기반 stem preservation (STEM_PRESERVE=0.85)
- 대각선 획 보존: paired-edge delta dampening으로 V/W/A/X 등 사선 획 왜곡 방지
- G1 tangent repair: zone 경계에서 곡선 연속성 보장
- Weight-dependent interaction deltas: Thin/Black별 wght×wdth 교차 보정
- SF Pro 기반 glyph whitelist: 텍스트 글리프만 폭 변형, 화살표/기호 등 고정폭 유지
- Letter-spacing sidebearing dampening (SB_DAMP=0.10)
- Single-stem guard (좁은 글리프 보호)
- named instances 27개 (Condensed/Normal/Expanded × 9 weights)
- STAT 테이블 width 축 등록

### 굵기 밸런스

- CJK weight 매핑: Pretendard native deltas 사용 (전 구간 회색도 평탄화)
- `_smooth_y_tail` 제거: Inter 원본 y tail geometry 유지 (spur 발생 방지)

### 웹/패키지

- CSS `font-stretch: 75% 125%` 지원
- Next.js `interlude-ui/font` wdth 지원
- Tailwind CSS v4 통합 (`font-opsz-text`, `font-opsz-display` 유틸리티)
- Dynamic Subset 지원 (variable + static)

### 빌드

- `make all`로 전체 파이프라인 실행 (다운로드 → 머지 → wdth → static → web)
- Static 폰트: 9 weights × 3 widths (Condensed/Normal/Expanded) × 2 optical sizes
- OS 자동 감지 폰트 설치 (`make install`)

## 1.1.0 (2025-06-04)

리브랜딩 + CJK 밸런스 보정.

### 브랜딩

- Inter CJK → **Interlude**로 폰트명 전면 변경
- vendorID: ICJK → INTL
- npm 패키지: `inter-cjk` → `interlude-ui`

### CJK 밸런스

- CJK 수직 스케일 1.029 적용 (Inter capHeight / Pretendard capHeight 비율 보정)
- CJK weight 매핑: wght=400에서 Pretendard wght=430 두께 사용
- Y_OFFSET 0으로 변경 (수직 스케일이 자연 정렬 처리)

### 빌드

- Inter/Pretendard 릴리즈 바이너리 다운로드 (submodule 완전 제거)
- `git clone` 한 방으로 빌드 가능

## 1.0.0 (2025-05-31)

정식 릴리즈.

- Inter 4.1 + Pretendard JP 1.3.9 기반 Variable 폰트 (opsz 14–32, wght 100–900)
- 22,981 글리프, Static 18파일, TTC, woff2, dynamic subset
- OpenType 53개 피처 (calt, ss05 Korean Localization, chws/halt 등)
- Next.js + CSS + npm 패키지 배포
