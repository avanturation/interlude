import localFont from "next/font/local";

export const Interlude = localFont({
  src: "../../../dist/woff2/InterludeVariable.woff2",
  variable: "--font-interlude",
  weight: "100 900",
  display: "swap",
  declarations: [{ prop: "font-stretch", value: "75% 125%" }],
  fallback: [
    "-apple-system", "BlinkMacSystemFont", "Apple SD Gothic Neo",
    "Segoe UI", "Roboto", "Helvetica Neue", "Noto Sans", "sans-serif",
  ],
});
