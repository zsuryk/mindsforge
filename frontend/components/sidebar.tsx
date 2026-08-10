"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Brain, Clapperboard, LayoutDashboard, ListVideo } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: ListVideo },
  { href: "/ab-experiments", label: "A/B Experiments", icon: BarChart3 },
  { href: "/memory-inspector", label: "Memory Inspector", icon: Brain },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60">
      <div className="flex items-center gap-2 border-b border-slate-800 px-6 py-5">
        <Clapperboard className="h-6 w-6 text-indigo-400" />
        <span className="text-lg font-semibold text-slate-100">MindsForge</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {navItems.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}