# Interlude

Interlude는 [Inter](https://rsms.me/inter)와 [Pretendard](https://github.com/orioncactus/pretendard)를 결합하고, UI 등 주요 사용 환경에 맞게 보정해 한국어, 일본어, 중국어까지 커버하는 서체입니다. Inter와 Pretendard가 지원하는 모든 OpenType 기능을 그대로 포함하며, 9가지 굵기와 가변 (Variable) 글꼴을 지원합니다.

[**최신 버전 다운로드하기**](https://github.com/avanturation/interlude/releases/latest)

<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/overview-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/overview.png">
  <img alt="overview" src="docs/overview.png">
</picture>

<br/>

## 기능 및 배경

자세한 배경과 OpenType 기능, Inter 및 Pretendard와의 차이점은 [이곳](https://avanturation.com/interlude)에서 확인하실 수 있습니다.

<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/why-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/why.png">
  <img alt="why" src="docs/why.png">
</picture>

<br/>

## Interlude 사용하기

[**최신 버전 다운로드하기**](https://github.com/avanturation/interlude/releases/latest)

### 웹 폰트로 사용하기

#### Variable (권장)

전체 글리프를 하나의 가변 폰트로 로드합니다.

```html
<link href="https://cdn.jsdelivr.net/npm/interlude-ui/dist/web/interlude-ui.css" rel="stylesheet">
```

이 CSS는 세 가지 `font-family`를 정의합니다.

- `Interlude Variable` — 가변 (opsz 14–32, wght 100–900, wdth 75–150)
- `Interlude` — 정적 본문용 (opsz 14)
- `Interlude Display` — 정적 제목용 (opsz 32)

#### Dynamic Subset (경량 로딩, 권장)

페이지에서 실제로 사용하는 글리프만 로드합니다. CJK 폰트의 용량 문제를 해결합니다.

Variable (하나의 폰트로 모든 굵기 커버):

```html
<link href="https://cdn.jsdelivr.net/npm/interlude-ui/dist/web/dynamic-subset/interlude-ui-variable-dynamic-subset.css" rel="stylesheet">
```

```css
body { font-family: "Interlude Variable", sans-serif; }
```

Static (가변 미지원 환경, 본문 `Interlude` / 제목 `Interlude Display`):

```html
<link href="https://cdn.jsdelivr.net/npm/interlude-ui/dist/web/dynamic-subset-static/interlude-ui-dynamic-subset.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/interlude-ui/dist/web/dynamic-subset-static/interlude-ui-display-dynamic-subset.css" rel="stylesheet">
```

```css
body { font-family: "Interlude", sans-serif; }
h1, h2, h3 { font-family: "Interlude Display", sans-serif; }
```

### Next.js에서 사용하기

```bash
npm install interlude-ui
```

```tsx
// app/layout.tsx
import { Interlude, InterludeDisplay } from "interlude-ui/font";

export default function RootLayout({ children }) {
  return (
    <html className={`${Interlude.variable} ${InterludeDisplay.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

```css
/* globals.css */
body {
  font-family: var(--font-interlude-ui), sans-serif;
}

h1, h2, h3 {
  font-family: var(--font-interlude-ui-display), sans-serif;
}
```

개별 import도 가능합니다:

```tsx
import { Interlude } from "interlude-ui/font/sans";
import { InterludeDisplay } from "interlude-ui/font/display";
```

### Tailwind CSS v4에서 사용하기

Tailwind v4는 CSS-first 설정이라, CSS 한 줄 import로 폰트 로드 + 토큰 등록이 끝납니다.

```css
@import "tailwindcss";
@import "interlude-ui/tailwind";
```

```html
<div class="font-sans">본문 Body</div>
<h1 class="font-display font-opsz-display">제목 Heading</h1>
```

`interlude-ui/tailwind`은 dynamic-subset `@font-face`를 로드하고, `@theme`로 `--font-sans` / `--font-display` 토큰과 optical size 유틸리티(`font-opsz-text`, `font-opsz-display`)를 등록합니다.

> 모든 `@import`는 다른 CSS 규칙보다 먼저 와야 합니다. 그렇지 않으면 `@font-face`가 드롭됩니다.

> 번들러(Vite, Next.js 등)는 폰트 `url()`을 자동으로 재배치하므로 그대로 동작합니다. 다만 Tailwind standalone CLI(`@tailwindcss/cli`)는 `@import` 인라인 시 `url()`을 재배치하지 않아 woff2 경로가 깨집니다. CLI만 쓰는 환경이라면 아래 CDN CSS를 직접 로드하세요.
>
> ```html
> <link href="https://cdn.jsdelivr.net/npm/interlude-ui/dist/web/dynamic-subset/interlude-ui-variable-dynamic-subset.css" rel="stylesheet">
> ```

## font-family

권장하는 `font-family` 조합은 아래와 같습니다.

```css
font-family: "Interlude Variable", "Interlude",
  -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo",
  "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", sans-serif,
  "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
```

### Display 사용하기

Interlude Variable은 하나의 파일에 Text(opsz=14)와 Display(opsz=32)를 모두 포함합니다.

```css
/* 본문 (기본, opsz=14) */
body {
  font-family: "Interlude Variable", sans-serif;
}

/* 제목/Hero (opsz=32) */
h1 {
  font-family: "Interlude Variable", sans-serif;
  font-variation-settings: 'opsz' 32;
}
```

Static 폰트에서는 별도 패밀리로 분리되어 있습니다:
- `Interlude` — 본문용
- `Interlude Display` — 제목용

<br/>

## Font Families

- **Interlude** — UI, 본문에 최적화 (optical size 14)
- **Interlude Display** — Display, Hero에 최적화 (optical size 32)

### Variable Axes

| Axis | Tag | Range | Default |
|------|-----|-------|---------|
| Optical Size | `opsz` | 14–32 | 14 |
| Weight | `wght` | 100–900 | 400 |
| Width | `wdth` | 75–150 | 100 |

### 언어 커버리지

- 라틴, 키릴, 그리스 문자 계열 (Inter 기반)
- 11,172자 한글 음절 (Pretendard 기반)
- 184자 히라가나 + 가타카나 (Pretendard 기반)
- 7,138자 CJK 통합 한자 (Pretendard 기반)
- CJK 기호·호환·반각/전각 문자 (Inter & Pretendard 혼합)

<br/>

## Build

Inter와 Pretendard의 릴리즈 바이너리를 다운로드한 후, Interlude 설계 원칙에 맞는 패치를 진행해 빌드합니다.

```bash
git clone https://github.com/avanturation/interlude-ui.git
python3 -m pip install -r requirements.txt
make clean
make all
```

<br/>

## Credits

- [Inter](https://rsms.me/inter/) by @rsms
- [Pretendard](https://github.com/orioncactus/pretendard) by @orioncactus

### Contribute

Interlude는 UI 디자이너로서 평소 가지고 있던 생각들을 조합해, `Glyphs`와 같은 서체 전용 툴 없이 OpenCode 만으로 제작되었습니다. 

폰트에 대한 지식이 부족한 만큼, 오픈소스 커뮤니티의 많은 피드백과 기여가 필요합니다. Issues와 Pull Request를 통해 기여해주시면 감사하겠습니다.

### License

[SIL Open Font License 1.1](LICENSE.txt)
