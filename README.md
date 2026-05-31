# Inter CJK

Inter CJK는 [Inter](https://rsms.me/inter)와 [Pretendard](https://github.com/orioncactus/pretendard)를 결합하고, UI 등 주요 사용 환경에 맞게 보정해 한국어, 일본어, 중국어까지 커버하는 서체입니다. Inter와 Pretendard가 지원하는 모든 OpenType 기능을 그대로 포함하며, 9가지 굵기와 가변 (Variable) 글꼴을 지원합니다.

[**최신 버전 다운로드하기**](https://github.com/avanturation/inter-cjk/releases/latest)

<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/overview-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/overview.png">
  <img alt="overview" src="docs/overview.png">
</picture>

<br/>

## 기능 및 배경

자세한 배경과 OpenType 기능, Inter 및 Pretendard와의 차이점은 [이곳](https://avanturation.com/inter-cjk)에서 확인하실 수 있습니다.

<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/why-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/why.png">
  <img alt="why" src="docs/why.png">
</picture>

<br/>

## Inter CJK 사용하기

[**최신 버전 다운로드하기**](https://github.com/avanturation/inter-cjk/releases/latest)

### 웹 폰트로 사용하기

#### Variable (권장)

```html
<link href="https://cdn.jsdelivr.net/npm/inter-cjk/dist/web/inter-cjk.css" rel="stylesheet">
```

#### Dynamic Subset (경량 로딩)

페이지에서 실제로 사용하는 글리프만 로드합니다. CJK 폰트의 용량 문제를 해결합니다.

```html
<link href="https://cdn.jsdelivr.net/npm/inter-cjk/dist/web/dynamic-subset/inter-cjk-variable-dynamic-subset.css" rel="stylesheet">
```

#### 개별 Weight (Static)

특정 굵기만 필요한 경우:

```html
<link href="https://cdn.jsdelivr.net/npm/inter-cjk/dist/web/InterCJK-Regular.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/inter-cjk/dist/web/InterCJK-Bold.css" rel="stylesheet">
```

### Next.js에서 사용하기

```bash
npm install inter-cjk
```

```tsx
// app/layout.tsx
import { InterCJK, InterCJKDisplay } from "inter-cjk/font";

export default function RootLayout({ children }) {
  return (
    <html className={`${InterCJK.variable} ${InterCJKDisplay.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

```css
/* globals.css */
body {
  font-family: var(--font-inter-cjk), sans-serif;
}

h1, h2, h3 {
  font-family: var(--font-inter-cjk-display), sans-serif;
}
```

개별 import도 가능합니다:

```tsx
import { InterCJK } from "inter-cjk/font/sans";
import { InterCJKDisplay } from "inter-cjk/font/display";
```

## font-family

권장하는 `font-family` 조합은 아래와 같습니다.

```css
font-family: "Inter CJK Variable", "Inter CJK",
  -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo",
  "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", sans-serif,
  "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
```

### Display 사용하기

Inter CJK Variable은 하나의 파일에 Text(opsz=14)와 Display(opsz=32)를 모두 포함합니다.

```css
/* 본문 (기본, opsz=14) */
body {
  font-family: "Inter CJK Variable", sans-serif;
}

/* 제목/Hero (opsz=32) */
h1 {
  font-family: "Inter CJK Variable", sans-serif;
  font-variation-settings: 'opsz' 32;
}
```

Static 폰트에서는 별도 패밀리로 분리되어 있습니다:
- `Inter CJK` — 본문용
- `Inter CJK Display` — 제목용

<br/>

## Font Families

- **Inter CJK** — UI, 본문에 최적화 (optical size 14)
- **Inter CJK Display** — Display, Hero에 최적화 (optical size 32)

### Variable Axes

| Axis | Tag | Range | Default |
|------|-----|-------|---------|
| Optical Size | `opsz` | 14–32 | 14 |
| Weight | `wght` | 100–900 | 400 |

### 언어 커버리지

- 라틴, 키릴, 그리스 문자 계열 (Inter 기반)
- 11,172자 한글 음절 (Pretendard 기반)
- 184자 히라가나 + 가타카나 (Pretendard 기반)
- 7,138자 CJK 통합 한자 (Pretendard 기반)
- CJK 기호·호환·반각/전각 문자 (Inter & Pretendard 혼합)

<br/>

## Build

Inter와 Pretendard의 릴리즈 바이너리를 다운로드한 후, Inter CJK 설계 원칙에 맞는 패치를 진행해 빌드합니다.

```bash
git clone --recurse-submodules https://github.com/avanturation/inter-cjk.git
python3 -m pip install -r requirements.txt
make clean
make all
```

<br/>

## Credits

- [Inter](https://rsms.me/inter/) by @rsms
- [Pretendard](https://github.com/orioncactus/pretendard) by @orioncactus

### Contribute

Inter CJK는 UI 디자이너로서 평소 가지고 있던 생각들을 조합해, `Glyphs`와 같은 서체 전용 툴 없이 OpenCode 만으로 제작되었습니다. 

폰트에 대한 지식이 부족한 만큼, 오픈소스 커뮤니티의 많은 피드백과 기여가 필요합니다. Issues와 Pull Request를 통해 기여해주시면 감사하겠습니다.

### License

[SIL Open Font License 1.1](LICENSE.txt)
