"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Brain, Flame, LayoutDashboard, ListVideo } from "lucide-react";

import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: ListVideo },
  { href: "/ab-experiments", label: "A/B Experiments", icon: BarChart3 },
  { href: "/memory-inspector", label: "Memory Inspector", icon: Brain },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border/40 bg-card/30">
      <div className="flex items-center gap-3 border-b border-border/40 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border/60 bg-primary text-primary-foreground">
          <Flame className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <p className="font-display text-base font-semibold tracking-tight text-foreground">
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
              className={cn(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-muted/70 text-foreground"
                  : "text-muted-foreground hover:bg-muted/40 hover:text-foreground",
              )}
            >
              <item.icon
                className={cn(
                  "h-4 w-4 transition-colors",
                  active
                    ? "text-primary"
                    : "text-subtle group-hover:text-muted-foreground",
                )}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border/40 p-3">
        <div className="rounded-lg border border-border/40 bg-card/60 p-3 backdrop-blur-md">
          <p className="text-xs font-medium text-foreground">Powered by Minds</p>
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            Persistent creator memory by Animoca Brands.
          </p>
        </div>
      </div>
    </aside>
  );
}
