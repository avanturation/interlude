

# Interlude

Interlude는 라틴과 CJK가 같은 화면 안에서 따로 튀지 않도록, 문자 사이의 밀도와 리듬을 다시 맞춘 인터페이스 서체입니다.

[Inter](https://rsms.me/inter)의 라틴 글리프와 [Pretendard](https://github.com/orioncactus/pretendard)의 CJK 글리프를 기반으로, 4px Grid 중심의 UI 환경에 맞게 폭과 밀도를 다시 조율했습니다. 라틴과 CJK가 함께 쓰일 때 생기는 크기감과 굵기 차이를 미세하게 조정해, 어느 한쪽이 튀지 않고 자연스럽게 읽히도록 맞췄습니다. 9가지 굵기와 wdth 축을 통한 Expanded & Condensed 너비 조절, Variable을 지원해 다양한 화면 밀도와 인터페이스 조건에 유연하게 대응합니다.

[**최신 버전 다운로드하기**](https://github.com/avanturation/interlude/releases/latest)

<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/avanturation/interlude/blob/main/docs/overview-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/avanturation/interlude/blob/main/docs/overview.png">
  <img alt="overview" src="https://github.com/avanturation/interlude/blob/main/docs/overview.png">
</picture>

<br/>

## 기능 및 배경

자세한 배경과 OpenType 기능, Inter 및 Pretendard와의 차이점은 [이곳](https://avanturation.com/interlude)에서 확인하실 수 있습니다.

## Interlude 사용하기

[**최신 버전 다운로드하기**](https://github.com/avanturation/interlude/releases/latest)

### 웹 폰트로 사용하기

#### Variable (권장)

전체 글리프를 하나의 가변 폰트로 로드합니다.

```html
<link href="https://cdn.jsdelivr.net/npm/interlude-ui/dist/css/interlude.css" rel="stylesheet">
```

이 CSS는 세 가지 `font-family`를 정의합니다.

- `Interlude Variable` — 가변 (opsz 14–32, wght 100–900, wdth 75–125)
- `Interlude` — 정적 본문용 (opsz 14)
- `Interlude Display` — 정적 제목용 (opsz 32)

#### Dynamic Subset

페이지에서 실제로 사용하는 글리프만 로드하며, CJK 폰트의 용량 문제를 해결합니다.

```html
 <link href="https://cdn.jsdelivr.net/npm/interlude-ui/dist/dynamic-subset/interlude-variable-dynamic-subset.css" rel="stylesheet">
```

```css
body { font-family: "Interlude Variable", sans-serif; }
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

```css
@import "tailwindcss";
@import "interlude-ui/tailwind";
```

```html
<div class="font-sans">본문 Body</div>
<h1 class="font-display font-opsz-display">제목 Heading</h1>
```

Dynamic Subset용 `@font-face`를 로드하고, `@theme`로 `--font-sans` / `--font-display` 토큰과 optical size 유틸리티(`font-opsz-text`, `font-opsz-display`)를 등록합니다.

`@font-face` 규칙이 정상적으로 적용되도록, 이 import는 CSS 파일의 가장 위에 두는 것을 권장합니다.

또한 Vite나 Next.js 같은 번들러는 폰트 경로를 자동으로 처리하지만, Tailwind standalone CLI 환경에서는 import된 폰트 URL이 제대로 재작성되지 않을 수 있습니다. 이런 경우, CDN의 CSS를 직접 불러와주세요.

 ```html
<link href="https://cdn.jsdelivr.net/npm/interlude-ui/dist/dynamic-subset/interlude-variable-dynamic-subset.css" rel="stylesheet">
 ```

## font-family

권장하는 `font-family` 조합은 아래와 같습니다.

```css
font-family: "Interlude Variable", "Interlude",
  -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo",
  "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", sans-serif,
  "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
```

### Display 사용하기

Interlude Variable은 하나의 파일에 Text `opsz=14` 와 Display `opsz=32` 를 모두 포함합니다.

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

## Font Families

- **Interlude** — UI, 본문에 최적화 (optical size 14)
- **Interlude Display** — Display, Hero에 최적화 (optical size 32)

### Variable Axes

| Axis | Tag | Range | Default |
|------|-----|-------|---------|
| Optical Size | `opsz` | 14–32 | 14 |
| Weight | `wght` | 100–900 | 400 |
| Width | `wdth` | 75–125 | 100 |

### 언어 커버리지

- 라틴, 키릴, 그리스 문자 계열 (Inter 기반)
- 11,172자 한글 음절 (Pretendard 기반)
- 184자 히라가나 + 가타카나 (Pretendard 기반)
- 7,138자 CJK 통합 한자 (Pretendard 기반)
- CJK 기호·호환·반각/전각 문자 (Inter & Pretendard 혼합)

## Build

Inter와 Pretendard의 릴리즈 바이너리를 다운로드한 후, Interlude 설계 원칙에 맞는 패치를 진행해 빌드합니다.

```bash
git clone https://github.com/avanturation/interlude.git
python3 -m pip install -r requirements.txt
make clean
make all
```

## Credits

- [Inter](https://rsms.me/inter/) by @rsms
- [Pretendard](https://github.com/orioncactus/pretendard) by @orioncactus

### Contribute

Interlude는 UI 디자이너로서 평소 가지고 있던 생각들을 조합해 서체 전용 툴 없이 OpenCode 만으로 제작되었습니다. 폰트에 대한 지식이 부족한 만큼, 오픈소스 커뮤니티의 많은 피드백과 기여가 필요합니다. Issues와 Pull Request를 통해 기여해주시면 감사하겠습니다.

### License

[SIL Open Font License 1.1](LICENSE.txt)
