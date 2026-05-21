import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans"
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono"
});

export const metadata: Metadata = {
  title: "CAMELS 분석 대시보드",
  description:
    "DRBC holdout에서 Model 1 deterministic LSTM과 Model 2 quantile LSTM 결과를 검토하는 Next.js 분석 대시보드입니다.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg"
  }
};

const themeScript = `
(function () {
  try {
    var key = "camels-dashboard-theme-v2";
    var saved = window.localStorage.getItem(key);
    var theme = saved === "light" || saved === "dark" ? saved : "dark";
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  } catch (_) {
    document.documentElement.dataset.theme = "dark";
    document.documentElement.style.colorScheme = "dark";
  }
})();
`;

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ko"
      className={`${geist.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
