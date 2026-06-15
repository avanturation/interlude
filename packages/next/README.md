# Interlude for Next.js

## 설치

```bash
npm install interlude-ui
```

## 사용법

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

개별 import도 가능:

```tsx
import { Interlude } from "interlude-ui/font/sans";
import { InterludeDisplay } from "interlude-ui/font/display";
```

## CSS에서 사용

```css
body {
  font-family: var(--font-interlude), sans-serif;
}

h1, h2, h3 {
  font-family: var(--font-interlude-display), sans-serif;
}
```

## CSS Variables

| Variable | 폰트 |
|----------|------|
| `--font-interlude` | Interlude (본문, opsz=14) |
| `--font-interlude-display` | Interlude Display (제목, opsz=32) |
