# wdth 50 (극단 축소) 지원 가능성 연구

> 상태: **연구 전용 (적용 안 함)**. 이 문서는 wdth 축을 50까지 내리는 것의 기술적 타당성만 분석합니다. SF Pro의 wdth ~50-150 범위를 참고 목표로 삼았습니다.

## 1. 핵심 결론 (TL;DR)

| 항목 | 결론 |
|---|---|
| 확장 (wdth 150) | ✅ 합성으로 production 품질 달성 — 이미 별도 작업(A)에서 구현 |
| 축소 (wdth 50) | ⚠️ 합성만으로는 한계. 엔진 재튜닝 필수, 그래도 곡선 글자는 품질 저하 |
| 렌더러 외삽(extrapolation) | ❌ **불가능**. gvar는 마스터 범위 밖을 외삽하지 않음. wdth=50을 쓰려면 50 지점에 **실제 마스터(gvar tuple)가 반드시 존재**해야 함 |
| 업계 관행 | 모든 production 가변폰트는 **~75%에서 합성 보간을 멈추고** 그 아래는 손으로 마스터를 그림 |

## 2. 왜 축소가 확장보다 어려운가 (비대칭성)

확장은 점들을 바깥으로 펼치기만 하므로 충돌이 없다. 축소는 outline을 서로 안쪽으로 밀어넣어 세 가지 고질적 문제를 일으킨다.

1. **Self-intersection (윤곽선 자기교차)** — 곡선 글리프(g, a, s, 1, 5, 6, 9)가 s=0.5에서 접힘. 실측: 대표 43자 중 6자 발생.
2. **카운터 메움 / 색 불균일** — 폭은 50%로 줄지만 stem multiplier는 0.902까지만 줄어, stem/폭 비율이 거의 2배가 됨. 닫힌 카운터(B/E/H/R)가 잉크로 메워져 텍스트가 어둡게 보임.
3. **보간 kink / 정수 반올림** — 극단 위치에서 TrueType 정수 좌표 반올림으로 핸들 정렬이 깨짐.

## 3. 결정적 제약: gvar 외삽 불가

OpenType `gvar`는 표준 렌더러(브라우저, OS, HarfBuzz)에서 **마스터 범위 밖을 외삽하지 않는다.**

- fontTools `VariationModel(extrapolate=False)`가 기본값이며, `extrapolate=True`는 **빌드타임 모델링 전용** (PR #2757). 렌더타임에는 적용되지 않음.
- CSS Fonts L4 명세: 요청한 width 값이 없으면 **가장 가까운 지원 값으로 clamp**. 외삽 의무 없음.

**함의**: fvar가 `wdth: min=75`로 정의되어 있으면 wdth=50 요청은 75로 clamp됨. wdth=50을 네이티브로 지원하려면 50(또는 그 이하) 지점에 마스터를 추가하는 수밖에 없다.

## 4. 업계는 어디서 마스터를 그리는가

| 폰트 / 시스템 | 최소 폭 | 전략 |
|---|---|---|
| Noto Sans | 62.5% | 4개 폭 마스터, 외삽 없음 |
| SF Pro (Apple) | ~65%(비공개) | 폭별 독립 마스터, narrow에서 opsz 재튜닝 |
| Gotham Variable (Monotype) | ~75% | 중간 마스터 다수, narrow에서 stroke ending 재배치 |
| Roboto Flex | 75% | width + GRAD축 병행으로 안정화 |

**패턴**: production 가변폰트는 예외 없이 **75-80%에서 합성을 멈추고** 그 아래는 손으로 그린 마스터를 사용. 25%를 넘는 폭 축소에서는 stem weight, 카운터 공간, ink trap 등 광학적 보정이 필수가 되기 때문.

## 5. 합성 축소를 더 밀어붙이는 기법

마스터를 못 그리는 경우 production이 쓰는 hybrid 전략:

1. **Stem weight 감쇠 곡선** — 폭 감소에 따라 stem을 더 공격적으로 thin.
2. **Ink trap 삽입** — V/W/접합부의 날카로운 안쪽 모서리에 의도적 trap을 넣어 카운터 메움 방지.
3. **Contour-aware 비균일 스케일** — stem-aware 인자로 X축만 따로 스케일 (RoboFont Condensomatic 패턴).
4. **UPM 상향** — 2000+ UPM으로 narrow 정밀도 확보 (Inter는 2816 UPM 사용).
5. **중간 마스터 추가** — 87.5% 등 핵심 지점에 마스터 추가.

## 6. 우리 엔진(Interlude)의 구체적 break point (s=0.5 실측)

`misc/wdth_displace.py`, `wdth_multipliers.py`, `wdth_stems.py` 분석 결과, 0.75-1.25 범위에 하드코딩된 파라미터들이 s=0.5에서 깨진다.

### 6.1 Multiplier 공식 (0.75-1.25 가정으로 fit됨)

- `latin_stem_multiplier(0.5) = 0.902` — 2차 곡선이 s≥0.75 가정으로 fit됨. s=0.5는 설계 의도 밖 외삽.
- `cjk_stem_multiplier`의 `(1.0-s)/0.25` 항이 s=0.5에서 2.0이 됨 — 정상 범위(0.75)의 2배 보너스가 적용되는 외삽.
- `sb_multiplier(0.5) = 0.70` — floor 없는 가파른 기울기.

### 6.2 Self-intersection 가드 (`displace_v2` L451-494)

- `_SELF_X_TOL = 2`로 너무 관대 → 6자 중 일부가 그냥 통과.
- fallback cascade의 `se += 0.05` 스텝이 너무 거칢 (s=0.5→0.55는 10% 점프).
- 가드는 `lam`(displacement)을 줄여 복구하지만, 그 과정에서 stem이 더 어두워짐.

### 6.3 Stem 측정 floor (`wdth_stems.py`)

- `MIN_STEM = 51.2` (0.025*UPM) — s=0.5에서 Latin stem이 ≈66.5로 floor에 근접. 이하로 떨어지면 측정 실패 → class median으로 fallback → 글리프별 stem 튜닝 무력화.
- `MIN_RUN=24.576`, `STEM_PRIOR=169.98`, `MODE_BIN=8.0` 모두 절대값이라 s=0.5에서 비례적으로 어긋남.

### 6.4 s=0.5에서 재튜닝이 필요한 파라미터 (요약)

| 파라미터 | 파일 | 현재값 | s=0.5 영향 |
|---|---|---|---|
| `_SELF_X_TOL` | wdth_displace.py:3 | 2 | 6자 자기교차 통과 → 8-12로 상향 검토 |
| `MIN_STEM` | wdth_stems.py | 51.2 | stem 측정 실패 → ~40으로 하향 |
| `STEM_PRIOR` | wdth_stems.py | 169.98 | narrow stem에 안 맞음 → ~85-90 |
| `(1.0-s)/0.25` | wdth_multipliers.py:38,40 | 0.25 고정 | piecewise/적응형 필요 |
| stem multiplier 곡선 | wdth_multipliers.py:13-17 | s≥0.75 fit | s<0.75 구간 재fit 필요 |
| `se += 0.05` | wdth_displace.py:490 | 0.05 | 0.02-0.03으로 세분화 |
| `lam_cap` | wdth_displace.py:301 | 5.0 | 10-15로 상향 검토 |

## 7. wdth 50을 제대로 하려면 (작업 견적)

1. **stem multiplier 재설계** — s<0.75 구간 곡선을 별도 fit. 곡선 글자의 `latin_stem(0.5)`를 0.902 → ~0.78로.
2. **self-x 가드 강화** — 곡선 글리프용 per-glyph relax + tolerance 재조정.
3. **stem 측정 floor 하향** + scale 비례화.
4. **CJK 축소 한계 검증** — `(1-s)/0.25` 정규화 재설계.
5. **곡선 글리프 ink trap / contour-aware 스케일** 도입 검토 (가장 어려운 부분).
6. **마스터 추가** — wdth=50 gvar tuple 필수. 폰트 용량 증가.

이는 며칠 단위 R&D이며, 5번(곡선 품질)은 합성만으로는 완전 해결이 어려울 수 있음 — 업계가 손으로 그리는 이유.

## 8. 추천 로드맵

- **단기 (완료/진행 중)**: 확장 150 추가 (별도 작업 A). 거의 무료, production 품질.
- **중기**: wdth=62.5~70 정도까지만 축소 확대 (Noto 수준). 엔진 재튜닝 비용 중간, 품질 확보 가능.
- **장기 (선택)**: wdth=50 풀 지원. 위 1-6 전부 + 곡선 글리프 품질 반복 검증. 비용 높음.

## 부록: 출처

- FontAlternatives, "Width Axis vs Condensed Family" — 75% 하한 가이드
- Adobe Type, "Designing Multiple Master Fonts" (5091) — 마스터 광학 보정
- Noto Weight-Width-Style Specification (GitHub notofonts) — 62.5% 하한, 4 마스터
- Apple WWDC22 #110381 — SF Pro 폭축 / opsz 결합
- fontTools PR #2757, varLib/models 문서 — 외삽은 빌드타임 전용
- W3C CSS Fonts L4 — 미지원 width는 clamp
- RoboFont Condensomatic — stem-aware X 스케일 패턴
</content>
</invoke>
