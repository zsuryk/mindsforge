import { JobStatus } from "@/lib/api";

const STATUS_CONFIG: Record<JobStatus, { className: string; inProgress: boolean }> = {
  PENDING: { className: "bg-amber-500/10 text-amber-300 border-amber-500/30", inProgress: true },
  DOWNLOADING: { className: "bg-sky-500/10 text-sky-300 border-sky-500/30", inProgress: true },
  TRANSCRIBING: { className: "bg-violet-500/10 text-violet-300 border-violet-500/30", inProgress: true },
  EXTRACTING_CLIPS: { className: "bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/30", inProgress: true },
  COMPLETED: { className: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30", inProgress: false },
  FAILED: { className: "bg-red-500/10 text-red-300 border-red-500/30", inProgress: false },
};

export function StatusBadge({
  status,
  animated = false,
}: {
  status: JobStatus;
  animated?: boolean;
}) {
  const config = STATUS_CONFIG[status];
  const pulsing = animated && config.inProgress;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${config.className}`}
    >
      {pulsing && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {status}
    </span>
  );
}
