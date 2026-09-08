import type { Metadata, Viewport } from "next";

import { AppShell } from "@/components/app-shell";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "LandTrust Connect — Trust every claim. Verify every transaction.",
    template: "%s · LandTrust Connect",
  },
  description:
    "An AI-based evidence-gated land ownership verification, secure owner interaction and " +
    "autonomous transaction risk resolution system. Research prototype — decision support " +
    "only, not an official land record.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#0f1c38",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/*
          Inter is loaded by link rather than `next/font/google` on purpose: that helper
          downloads the font at build time, so a machine without internet access cannot
          build the project at all. Loaded this way, an offline machine simply falls back
          to the system sans stack declared in tailwind.config.ts and everything still works.
        */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
