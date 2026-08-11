"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Upload } from "lucide-react";

import { Job, JobStatus, fetchJobs, submitJob } from "@/lib/api";

const BADGE_CLASSES: Record<JobStatus, string> = {
  PENDING: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  DOWNLOADING: "bg-sky-500/10 text-sky-300 border-sky-500/30",
  TRANSCRIBING: "bg-violet-500/10 text-violet-300 border-violet-500/30",
  EXTRACTING_CLIPS: "bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/30",
  COMPLETED: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  FAILED: "bg-red-500/10 text-red-300 border-red-500/30",
};

function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${BADGE_CLASSES[status]}`}
    >
      {status}
    </span>
  );
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [title, setTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold text-slate-100">Jobs</h1>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-5"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="source-url" className="text-sm font-medium text-slate-300">
              Source URL
            </label>
            <input
              id="source-url"
              type="text"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              placeholder="https://youtube.com/watch?v=…"
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="title" className="text-sm font-medium text-slate-300">
              Title
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Optional — defaults to URL or filename"
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <label
            htmlFor="file"
            className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300 hover:border-indigo-500"
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
            className="rounded-lg bg-indigo-500 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit job"}
          </button>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}
      </form>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-slate-400">Submitted jobs</h2>
        {jobs.length === 0 ? (
          <p className="text-sm text-slate-500">No jobs yet — submit your first source above.</p>
        ) : (
          <ul className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900">
            {jobs.map((job) => (
              <li key={job.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-100">{job.title}</p>
                  <p className="truncate text-xs text-slate-500">
                    {job.source_url ?? job.file_path ?? "—"}
                  </p>
                  {job.status === "FAILED" && job.error_message && (
                    <p className="mt-1 truncate text-xs text-red-400">{job.error_message}</p>
                  )}
                  {job.status === "TRANSCRIBING" &&
                    job.transcript_segments &&
                    job.transcript_segments.length > 0 && (
                      <p className="mt-1 text-xs text-slate-500">
                        {job.transcript_segments.length} segments · {job.duration_seconds?.toFixed(1)}s
                      </p>
                    )}
                </div>
                <StatusBadge status={job.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}