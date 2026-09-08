import type { Metadata } from "next";
import { Providers } from "@/components/layout/providers";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";
export const metadata: Metadata = {
  title: "FORGE — Agent console",
  description: "Build, version, and inspect your local FORGE agents.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
