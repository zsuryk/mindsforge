"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RotateCcw, Trash2, Upload } from "lucide-react";

import JobClips from "@/components/job-clips";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    <div className="mx-auto max-w-7xl space-y-8">
      <header>
        <Badge variant="outline" className="uppercase tracking-[0.18em] text-xs">
          Studio
        </Badge>
        <h1 className="mt-4 font-display text-3xl font-semibold tracking-tight text-foreground">
          Jobs
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Submit a long-form source and track it through the ingestion pipeline.
        </p>
      </header>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-sm font-semibold">New source</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="source-url">Source URL</Label>
                <Input
                  id="source-url"
                  type="text"
                  value={sourceUrl}
                  onChange={(event) => setSourceUrl(event.target.value)}
                  placeholder="https://youtube.com/watch?v=…"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Optional — defaults to URL or filename"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload />
                {file ? file.name : "Upload a media file"}
              </Button>
              <input
                id="file"
                ref={fileInputRef}
                type="file"
                accept="video/*,audio/*"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                className="hidden"
              />

              <Button type="submit" disabled={submitting} className="ml-auto">
                {submitting ? "Submitting…" : "Submit job"}
              </Button>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      </form>

      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-foreground">Submitted jobs</h2>
        {jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No jobs yet — submit your first source above.
          </p>
        ) : (
          <Card>
            <ul className="divide-y divide-border/40">
              {jobs.map((job) => (
                <li key={job.id} className="divide-y divide-border/40">
                  <div className="flex items-center justify-between gap-4 px-6 py-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{job.title}</p>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {job.source_url ?? job.file_path ?? "—"}
                      </p>
                      {job.status === "FAILED" && job.error_message && (
                        <p className="mt-1 truncate text-xs text-destructive">{job.error_message}</p>
                      )}
                      {job.status === "TRANSCRIBING" &&
                        job.transcript_segments &&
                        job.transcript_segments.length > 0 && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            {job.transcript_segments.length} segments ·{" "}
                            {job.duration_seconds?.toFixed(1)}s
                          </p>
                        )}
                      {job.status === "COMPLETED" && (
                        <p className="mt-1 text-xs text-muted-foreground">Clips ready</p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <StatusBadge status={job.status} />
                      {!IN_PROGRESS_STATUSES.has(job.status) && (
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          onClick={() => handleRetry(job.id)}
                          disabled={busyJobId === job.id}
                          aria-label="Retry job"
                          title="Retry"
                        >
                          <RotateCcw />
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        onClick={() => handleDelete(job.id)}
                        disabled={busyJobId === job.id}
                        aria-label="Delete job"
                        title="Delete"
                        className="hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </div>
                  {job.status === "COMPLETED" && <JobClips jobId={job.id} />}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>
    </div>
  );
}
