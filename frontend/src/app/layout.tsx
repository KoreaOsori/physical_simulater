import type { Metadata } from "next";
import { DM_Mono, Noto_Sans_KR } from "next/font/google";
import "./globals.css";

const dmMono = DM_Mono({
  variable: "--font-dm-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

const notoSansKr = Noto_Sans_KR({
  variable: "--font-noto-sans-kr",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "신경 / 선충 연구소",
  description: "C. elegans 커넥톰 기반 신경 신호 전파 · 신경전달물질 · 행동 발현 시뮬레이터",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className={`${dmMono.variable} ${notoSansKr.variable} h-full`}>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
