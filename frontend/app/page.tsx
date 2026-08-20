"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bell,
  BookMarked,
  Brain,
  CheckCircle2,
  FlaskConical,
  Link2,
  ListVideo,
  LucideIcon,
  Scissors,
  Sparkles,
  TrendingUp,
  Trophy,
  XCircle,
  Zap,
} from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  DashboardStats,
  fetchDashboardStats,
  fetchJobs,
  fetchMindActivity,
  Job,
  MindActivity,
  submitJob,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 5000;
const RECENT_JOB_COUNT = 5;

function MetricCard({
  label,
  icon: Icon,
  value,
}: {
  label: string;
  icon: LucideIcon;
  value: string;
}) {
  return (
    <Card className="group transition-colors hover:border-border">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border/40 bg-secondary/50">
            <Icon className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
          </div>
        </div>
        <p className="mt-5 text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 font-display text-3xl font-semibold tracking-tight text-foreground">
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

function formatCount(value: number | undefined): string {
  return value === undefined ? "—" : value.toLocaleString("en-US");
}

function formatAvg(value: number | null | undefined): string {
  return value === undefined || value === null ? "—" : value.toFixed(1);
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const ACTIVITY_ICONS: Record<string, LucideIcon> = {
  "clip-scored": Scissors,
  "experiment-sweep": FlaskConical,
  "experiment-concluded": Trophy,
  "experiment-failed": XCircle,
  "adaptation-ready": CheckCircle2,
  "adaptation-failed": AlertTriangle,
  "trend-researched": TrendingUp,
  "rule-saved": BookMarked,
  "mind-notified": Bell,
};

function formatRelativeTime(iso: string, now: number): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function MindAtWorkPanel({ events }: { events: MindActivity[] }) {
  const now = Date.now();
  const sorted = [...events].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 p-6 pb-4">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <span className="flex h-2 w-2 rounded-full bg-mind shadow-[0_0_8px_theme(colors.mind)]" />
          Mind at Work
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {sorted.length === 0 ? (
          <p className="px-6 pb-6 text-sm text-muted-foreground">
            The Mind is idle — submit a job to see it work.
          </p>
        ) : (
          <ul className="divide-y divide-border/40">
            {sorted.map((event, index) => {
              const Icon = ACTIVITY_ICONS[event.event_type] ?? Brain;
              return (
                <li
                  key={event.id}
                  data-testid={`activity-row-${event.event_type}`}
                  className={cn(
                    "flex items-start gap-3 px-6 py-3",
                    index === 0 && "bg-mind/5 ring-1 ring-inset ring-mind/20",
                  )}
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/40 bg-secondary/50">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-foreground">{event.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatRelativeTime(event.created_at, now)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activity, setActivity] = useState<MindActivity[]>([]);
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStats(await fetchDashboardStats());
    } catch {
      // keep the last known stats when the poll fails
    }
    try {
      setJobs(await fetchJobs());
    } catch {
      // keep the last known list when the poll fails
    }
    try {
      setActivity(await fetchMindActivity());
    } catch {
      // keep the last known activity when the poll fails
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;

    const sourceUrl = url.trim();
    if (!sourceUrl) {
      setSubmitError("Paste a video URL to process.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitJob({ sourceUrl });
      router.push("/jobs");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const recentJobs = jobs.slice(0, RECENT_JOB_COUNT);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <header>
        <Badge variant="outline" className="uppercase tracking-[0.18em] text-xs">
          MindsForge Studio
        </Badge>
        <h1 className="mt-4 font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          Turn long-form content into{" "}
          <span className="text-gradient">high-converting clips</span>
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Paste a source, and the Mind finds the golden moments, adapts them for every
          platform, and tests them autonomously.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="flex items-center gap-3">
        <Card className="flex flex-1 items-center gap-3 p-2 transition-colors focus-within:border-border">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-secondary/50">
            <Link2 className="h-4 w-4 text-muted-foreground" />
          </div>
          <Input
            type="text"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="Paste a video URL — press Enter to process it"
            aria-label="Video URL"
            className="border-0 bg-transparent shadow-none focus-visible:ring-0 placeholder:text-subtle"
          />
        </Card>
        <Button type="submit" disabled={submitting} size="lg" className="shrink-0">
          <Zap />
          {submitting ? "Starting…" : "Process"}
        </Button>
      </form>
      {submitError && <p className="text-sm text-destructive">{submitError}</p>}

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:col-span-2">
          <MetricCard label="Total Clips" icon={ListVideo} value={formatCount(stats?.total_clips)} />
          <MetricCard
            label="Active A/B Tests"
            icon={FlaskConical}
            value={formatCount(stats?.active_ab_tests)}
          />
          <MetricCard label="Avg Virality" icon={Sparkles} value={formatAvg(stats?.avg_virality)} />
          <MetricCard label="Total Insights" icon={Brain} value={formatCount(stats?.total_insights)} />
        </div>
        <MindAtWorkPanel events={activity} />
      </section>

      <section>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0 p-6 pb-4">
            <CardTitle className="text-sm font-semibold">Recent jobs</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/jobs">
                View all
                <ArrowUpRight />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {recentJobs.length === 0 ? (
              <p className="px-6 pb-6 text-sm text-muted-foreground">
                No jobs yet — paste a URL above to create your first clips.
              </p>
            ) : (
              <ul className="divide-y divide-border/40">
                {recentJobs.map((job) => (
                  <li key={job.id} className="transition-colors hover:bg-muted/30">
                    <Link href="/jobs" className="flex items-center gap-4 px-6 py-4">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-foreground">
                          {job.title}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          {job.source_url ?? job.file_path ?? "—"}
                        </p>
                      </div>
                      <StatusBadge status={job.status} animated />
                      <span className="hidden w-32 shrink-0 text-right text-xs text-muted-foreground sm:block">
                        {formatTimestamp(job.created_at)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
