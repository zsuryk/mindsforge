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
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <Icon className="mb-3 h-5 w-5 text-indigo-400" />
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-100">{value}</p>
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
        <h1 className="text-2xl font-semibold text-slate-100">MindsForge Studio</h1>
        <p className="text-sm text-slate-500">
          Turn long-form content into high-converting short clips.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900 p-3"
      >
        <Link2 className="h-5 w-5 shrink-0 text-indigo-400" />
        <input
          type="text"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="Paste a video URL — press Enter to process it"
          aria-label="Video URL"
          className="min-w-0 flex-1 bg-transparent text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none"
        />
        <button
          type="submit"
          disabled={submitting}
          className="flex shrink-0 items-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
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
        <h2 className="text-sm font-medium text-slate-400">Recent jobs</h2>
        {recentJobs.length === 0 ? (
          <p className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-sm text-slate-500">
            No jobs yet — paste a URL above to create your first clips.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Job</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="hidden px-5 py-3 font-medium sm:table-cell">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {recentJobs.map((job) => (
                  <tr key={job.id} className="transition-colors hover:bg-slate-950/50">
                    <td className="px-5 py-3">
                      <Link href="/jobs" className="block">
                        <p className="truncate font-medium text-slate-100 hover:text-indigo-300">
                          {job.title}
                        </p>
                        <p className="truncate text-xs text-slate-500">
                          {job.source_url ?? job.file_path ?? "—"}
                        </p>
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={job.status} animated />
                    </td>
                    <td className="hidden px-5 py-3 text-xs text-slate-500 sm:table-cell">
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
