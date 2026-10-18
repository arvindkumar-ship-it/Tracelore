import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";
export const metadata: Metadata = {
  title: "Tracelore · System observatory",
  description: "Observed state, evidence, and deterministic what-if analysis.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          rel="preload"
          href="/fonts/inter-latin.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
