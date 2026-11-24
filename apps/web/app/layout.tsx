import type { Metadata } from "next";
import "./globals.css";
import { TesseractBackground } from "@/components/tesseract-background";
export const metadata: Metadata = { title: "RepoPilot | Issue inbox", description: "A reliable starting point for repository investigation." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><TesseractBackground /><div className="app-content">{children}</div></body></html>;
}
