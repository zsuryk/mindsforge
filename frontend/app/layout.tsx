import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { SystemStatus } from "@/components/system-status";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-space" });

export const metadata: Metadata = {
  title: "MindsForge",
  description: "Turn long-form content into high-converting short clips.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${spaceGrotesk.variable} bg-background font-sans text-foreground antialiased`}
      >
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="bg-atmosphere sticky top-0 z-10 flex h-14 items-center justify-end border-b border-border/40 bg-background/60 px-6 backdrop-blur-md lg:px-8">
              <SystemStatus />
            </header>
            <main className="flex-1 px-6 py-8 lg:px-8">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
