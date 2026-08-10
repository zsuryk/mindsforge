import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { SystemStatus } from "@/components/system-status";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "MindsForge",
  description: "AI-driven creator platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-100 antialiased`}>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex flex-1 flex-col">
            <header className="sticky top-0 z-10 flex items-center justify-end border-b border-slate-800 bg-slate-950/80 px-8 py-4 backdrop-blur">
              <SystemStatus />
            </header>
            <main className="flex-1 px-8 py-8">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}