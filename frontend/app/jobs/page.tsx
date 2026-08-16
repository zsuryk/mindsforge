"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RotateCcw, Trash2, Upload } from "lucide-react";

import JobClips from "@/components/job-clips";
import { StatusBadge } from "@/components/status-badge";
import { Job, deleteJob, fetchJobs, retryJob, submitJob } from "@/lib/api";

const IN_PROGRESS_STATUSES = new Set([
  "PENDING",
  "DOWNLOADING",
  "TRANSCRIBING",
  "EXTRACTING_CLIPS",
]);

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [title, setTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setJobs(await fetchJobs());
    } catch {
      // keep the last known list when the poll fails
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;

    if (!sourceUrl && !file) {
      setError("Provide a source URL or a media file.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await submitJob({ title: title || undefined, sourceUrl: sourceUrl || undefined, file: file ?? undefined });
      setTitle("");
      setSourceUrl("");
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = async (jobId: string) => {
    setBusyJobId(jobId);
    setError(null);
    try {
      await retryJob(jobId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry failed.");
    } finally {
      setBusyJobId(null);
    }
  };

  const handleDelete = async (jobId: string) => {
    setBusyJobId(jobId);
    setError(null);
    try {
      await deleteJob(jobId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setBusyJobId(null);
    }
  };

  return (
    <div className="space-y-8">
      <header>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">
          Studio
        </p>
        <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight text-fg">
          Jobs
        </h1>
        <p className="mt-2 text-sm text-muted">
          Submit a long-form source and track it through the ingestion pipeline.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-xl border border-edge bg-card p-5"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="source-url" className="text-sm font-medium text-muted">
              Source URL
            </label>
            <input
              id="source-url"
              type="text"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              placeholder="https://youtube.com/watch?v=…"
              className="w-full rounded-lg border border-edge-strong bg-background px-3 py-2 text-sm text-fg placeholder:text-subtle focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="title" className="text-sm font-medium text-muted">
              Title
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Optional — defaults to URL or filename"
              className="w-full rounded-lg border border-edge-strong bg-background px-3 py-2 text-sm text-fg placeholder:text-subtle focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <label
            htmlFor="file"
            className="flex cursor-pointer items-center gap-2 rounded-lg border border-edge-strong bg-background px-3 py-2 text-sm text-muted transition-colors hover:border-accent"
          >
            <Upload className="h-4 w-4" />
            {file ? file.name : "Upload a media file"}
            <input
              id="file"
              ref={fileInputRef}
              type="file"
              accept="video/*,audio/*"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="hidden"
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-accent-foreground transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit job"}
          </button>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}
      </form>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-fg">Submitted jobs</h2>
        {jobs.length === 0 ? (
          <p className="text-sm text-subtle">No jobs yet — submit your first source above.</p>
        ) : (
          <ul className="divide-y divide-edge rounded-xl border border-edge bg-card">
            {jobs.map((job) => (
              <li key={job.id} className="divide-y divide-edge">
                <div className="flex items-center justify-between gap-4 px-5 py-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-fg">{job.title}</p>
                    <p className="truncate text-xs text-subtle">
                      {job.source_url ?? job.file_path ?? "—"}
                    </p>
                    {job.status === "FAILED" && job.error_message && (
                      <p className="mt-1 truncate text-xs text-red-400">{job.error_message}</p>
                    )}
                    {job.status === "TRANSCRIBING" &&
                      job.transcript_segments &&
                      job.transcript_segments.length > 0 && (
                        <p className="mt-1 text-xs text-subtle">
                          {job.transcript_segments.length} segments ·{" "}
                          {job.duration_seconds?.toFixed(1)}s
                        </p>
                      )}
                    {job.status === "COMPLETED" && (
                      <p className="mt-1 text-xs text-subtle">Clips ready</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <StatusBadge status={job.status} />
                    {!IN_PROGRESS_STATUSES.has(job.status) && (
                      <button
                        type="button"
                        onClick={() => handleRetry(job.id)}
                        disabled={busyJobId === job.id}
                        aria-label="Retry job"
                        title="Retry"
                        className="rounded-lg border border-edge-strong bg-background p-2 text-muted transition-colors hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDelete(job.id)}
                      disabled={busyJobId === job.id}
                      aria-label="Delete job"
                      title="Delete"
                      className="rounded-lg border border-edge-strong bg-background p-2 text-muted transition-colors hover:border-red-500 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                {job.status === "COMPLETED" && <JobClips jobId={job.id} />}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
