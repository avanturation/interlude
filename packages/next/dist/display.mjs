import localFont from "next/font/local";

export const InterCJKDisplay = localFont({
  src: "./fonts/InterCJKVariable.woff2",
  variable: "--font-inter-cjk-display",
  weight: "100 900",
  display: "swap",
  declarations: [{ prop: "font-variation-settings", value: "'opsz' 32" }],
  fallback: [
    "-apple-system", "BlinkMacSystemFont", "Apple SD Gothic Neo",
    "Segoe UI", "Roboto", "Helvetica Neue", "Noto Sans", "sans-serif",
  ],
});
