"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Brain, Flame, LayoutDashboard, ListVideo } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: ListVideo },
  { href: "/ab-experiments", label: "A/B Experiments", icon: BarChart3 },
  { href: "/memory-inspector", label: "Memory Inspector", icon: Brain },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-edge bg-surface">
      <div className="flex items-center gap-3 border-b border-edge px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent-hover shadow-lg shadow-accent/20">
          <Flame className="h-5 w-5 text-accent-foreground" />
        </div>
        <div className="leading-tight">
          <p className="font-display text-base font-semibold tracking-tight text-fg">
            MindsForge
          </p>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">
            Creator studio
          </p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-3">
        <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">
          Studio
        </p>
        {navItems.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-accent/10 text-fg"
                  : "text-muted hover:bg-elevated hover:text-fg"
              }`}
            >
              <span
                className={`absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent transition-opacity ${
                  active ? "opacity-100" : "opacity-0"
                }`}
              />
              <item.icon
                className={`h-4 w-4 transition-colors ${
                  active ? "text-accent" : "text-subtle group-hover:text-muted"
                }`}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-edge p-3">
        <div className="rounded-lg border border-edge bg-card p-3">
          <p className="text-xs font-medium text-fg">Powered by Minds</p>
          <p className="mt-1 text-[11px] leading-relaxed text-subtle">
            Persistent creator memory by Animoca Brands.
          </p>
        </div>
      </div>
    </aside>
  );
}
