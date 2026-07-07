# 변경 이력

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
