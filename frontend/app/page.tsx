"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Brain, FlaskConical, Link2, ListVideo, LucideIcon, Sparkles, Zap } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { DashboardStats, Job, fetchDashboardStats, fetchJobs, submitJob } from "@/lib/api";

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
    <div className="group rounded-xl border border-edge bg-card p-5 transition-colors hover:border-edge-strong">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-edge bg-elevated">
        <Icon className="h-5 w-5 text-accent" />
      </div>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 font-display text-3xl font-semibold text-fg">{value}</p>
    </div>
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

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
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
    <div className="space-y-8">
      <header>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">
          MindsForge Studio
        </p>
        <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight text-fg">
          Turn long-form content into{" "}
          <span className="text-gradient">high-converting clips</span>
        </h1>
        <p className="mt-2 text-sm text-muted">
          Paste a source, and the Mind finds the golden moments, adapts them for every
          platform, and tests them autonomously.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-3 rounded-xl border border-edge bg-card p-3 transition-colors focus-within:border-accent/50"
      >
        <Link2 className="h-5 w-5 shrink-0 text-accent" />
        <input
          type="text"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="Paste a video URL — press Enter to process it"
          aria-label="Video URL"
          className="min-w-0 flex-1 bg-transparent text-sm text-fg placeholder:text-subtle focus:outline-none"
        />
        <button
          type="submit"
          disabled={submitting}
          className="flex shrink-0 items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Zap className="h-4 w-4" />
          {submitting ? "Starting…" : "Process"}
        </button>
      </form>
      {submitError && <p className="text-sm text-red-400">{submitError}</p>}

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard label="Total Clips" icon={ListVideo} value={formatCount(stats?.total_clips)} />
        <MetricCard
          label="Active A/B Tests"
          icon={FlaskConical}
          value={formatCount(stats?.active_ab_tests)}
        />
        <MetricCard label="Avg Virality" icon={Sparkles} value={formatAvg(stats?.avg_virality)} />
        <MetricCard label="Total Insights" icon={Brain} value={formatCount(stats?.total_insights)} />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-fg">Recent jobs</h2>
        {recentJobs.length === 0 ? (
          <p className="rounded-xl border border-edge bg-card p-5 text-sm text-subtle">
            No jobs yet — paste a URL above to create your first clips.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-edge bg-card">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-edge text-xs uppercase tracking-wider text-subtle">
                <tr>
                  <th className="px-5 py-3 font-medium">Job</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="hidden px-5 py-3 font-medium sm:table-cell">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-edge">
                {recentJobs.map((job) => (
                  <tr key={job.id} className="transition-colors hover:bg-elevated/50">
                    <td className="px-5 py-3">
                      <Link href="/jobs" className="block">
                        <p className="truncate font-medium text-fg hover:text-accent">
                          {job.title}
                        </p>
                        <p className="truncate text-xs text-subtle">
                          {job.source_url ?? job.file_path ?? "—"}
                        </p>
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={job.status} animated />
                    </td>
                    <td className="hidden px-5 py-3 text-xs text-subtle sm:table-cell">
                      {formatTimestamp(job.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
