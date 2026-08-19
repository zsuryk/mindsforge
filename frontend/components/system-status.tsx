"use client";

import { useEffect, useState } from "react";
import { fetchHealth, type MindsStatus } from "@/lib/api";

type BackendState = "online" | "offline" | "checking";
type MindState = MindsStatus | "checking";

const BACKEND_STATE_CONFIG: Record<BackendState, { dotClass: string; label: string }> = {
  online: { dotClass: "bg-emerald-400", label: "Backend online" },
  offline: { dotClass: "bg-red-400", label: "Backend offline" },
  checking: { dotClass: "bg-amber-400 animate-pulse", label: "Checking…" },
};

const MIND_STATE_CONFIG: Record<MindState, { dotClass: string; label: string }> = {
  ok: { dotClass: "bg-emerald-400", label: "Mind online" },
  down: { dotClass: "bg-red-400", label: "Mind offline" },
  unconfigured: { dotClass: "bg-zinc-400", label: "Mind unconfigured" },
  checking: { dotClass: "bg-amber-400 animate-pulse", label: "Checking…" },
};

export function SystemStatus() {
  const [backendState, setBackendState] = useState<BackendState>("checking");
  const [mindState, setMindState] = useState<MindState>("checking");

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const health = await fetchHealth();
        if (!cancelled) {
          setBackendState(health.status === "ok" ? "online" : "offline");
          setMindState(health.minds);
        }
      } catch {
        if (!cancelled) {
          setBackendState("offline");
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

  const backend = BACKEND_STATE_CONFIG[backendState];
  const mind = MIND_STATE_CONFIG[mindState];

  return (
    <div className="flex items-center gap-2">
      <Pill dotClass={backend.dotClass} label={backend.label} title="Live status from the backend health endpoint" />
      <Pill dotClass={mind.dotClass} label={mind.label} title="Live status of the Mind's Builder API" />
    </div>
  );
}

function Pill({
  dotClass,
  label,
  title,
}: {
  dotClass: string;
  label: string;
  title: string;
}) {
  return (
    <div
      className="flex items-center gap-2 rounded-full border border-border/40 bg-card/60 px-3 py-1.5 text-sm text-muted-foreground backdrop-blur-md"
      title={title}
    >
      <span className={`h-2 w-2 rounded-full ${dotClass}`} />
      {label}
    </div>
  );
}