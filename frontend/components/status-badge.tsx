import { JobStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

const STATUS_CONFIG: Record<JobStatus, { className: string; inProgress: boolean }> = {
  PENDING: { className: "border-amber-500/30 bg-amber-500/10 text-amber-300", inProgress: true },
  DOWNLOADING: { className: "border-sky-500/30 bg-sky-500/10 text-sky-300", inProgress: true },
  TRANSCRIBING: { className: "border-violet-500/30 bg-violet-500/10 text-violet-300", inProgress: true },
  EXTRACTING_CLIPS: { className: "border-fuchsia-500/30 bg-fuchsia-500/10 text-fuchsia-300", inProgress: true },
  COMPLETED: { className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", inProgress: false },
  FAILED: { className: "border-red-500/30 bg-red-500/10 text-red-300", inProgress: false },
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
    <Badge variant="outline" className={cn(config.className, "shrink-0")}>
      {pulsing && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {status}
    </Badge>
  );
}
