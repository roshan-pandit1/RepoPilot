import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "RepoPilot | Issue inbox", description: "A reliable starting point for repository investigation." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
