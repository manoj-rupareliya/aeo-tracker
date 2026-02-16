import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "llmscm.com - LLM Visibility & Citation Intelligence",
  description:
    "Track how LLMs mention your brand, see which sources they cite, and measure visibility over time.",
  keywords: ["LLM", "AI", "SEO", "GEO", "Brand Visibility", "Citation Tracking"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className={`${inter.className} h-full bg-gray-50`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
