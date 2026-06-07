import localFont from "next/font/local";

export const InterludeDisplay = localFont({
  src: "./fonts/InterludeVariable.woff2",
  variable: "--font-interlude-display",
  weight: "100 900",
  display: "swap",
  declarations: [
    { prop: "font-stretch", value: "75% 150%" },
    { prop: "font-variation-settings", value: "'opsz' 32" },
  ],
  fallback: [
    "-apple-system", "BlinkMacSystemFont", "Apple SD Gothic Neo",
    "Segoe UI", "Roboto", "Helvetica Neue", "Noto Sans", "sans-serif",
  ],
});
