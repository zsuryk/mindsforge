"use client";

import { useEffect, useState } from "react";
import { fetchHealth } from "@/lib/api";

type SystemState = "online" | "offline" | "checking";

const STATE_CONFIG: Record<SystemState, { dotClass: string; label: string }> = {
  online: { dotClass: "bg-emerald-400", label: "Backend online" },
  offline: { dotClass: "bg-red-400", label: "Backend offline" },
  checking: { dotClass: "bg-amber-400 animate-pulse", label: "Checking…" },
};

export function SystemStatus() {
  const [state, setState] = useState<SystemState>("checking");

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const health = await fetchHealth();
        if (!cancelled) {
          setState(health.status === "ok" ? "online" : "offline");
        }
      } catch {
        if (!cancelled) {
          setState("offline");
        }
      }
    };

    check();
    const interval = setInterval(check, 10_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const { dotClass, label } = STATE_CONFIG[state];

  return (
    <div
      className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-300"
      title="Live status from the backend health endpoint"
    >
      <span className={`h-2 w-2 rounded-full ${dotClass}`} />
      {label}
    </div>
  );
}