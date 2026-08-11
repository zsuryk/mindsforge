export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

export function mediaUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  const origin = API_URL.replace(/\/api\/v1\/?$/, "");
  return `${origin}${path}`;
}

export type HealthStatus = {
  status: "ok" | "degraded" | "down";
  service: string;
  timestamp: string;
};

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

export type JobStatus =
  | "PENDING"
  | "DOWNLOADING"
  | "TRANSCRIBING"
  | "EXTRACTING_CLIPS"
  | "COMPLETED"
  | "FAILED";

export type TranscriptSegment = {
  text: string;
  start: number;
  end: number;
};

export type Job = {
  id: string;
  title: string;
  source_url: string | null;
  file_path: string | null;
  status: JobStatus;
  duration_seconds: number | null;
  transcript_segments: TranscriptSegment[] | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type JobCreated = {
  job_id: string;
  status: JobStatus;
  message: string;
};

export type PlatformHooks = {
  youtube_shorts: string[];
  tiktok: string[];
  x: string[];
};

export type ClipMetadata = {
  virality_score: number;
  suggested_titles: string[];
  platform_hooks: PlatformHooks;
};

export type Clip = {
  id: string;
  job_id: string;
  title: string;
  start_time: number;
  end_time: number;
  transcript_text: string;
  video_url: string;
  thumbnail_url: string | null;
  virality_score: number | null;
  suggested_hooks: ClipMetadata | null;
  created_at: string;
};

export type SubmitJobInput = {
  title?: string;
  sourceUrl?: string;
  file?: File;
};

async function extractError(res: Response): Promise<Error> {
  let message = `Request failed with status ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") {
      message = body.detail;
    }
  } catch {
    // keep the status-based message when the body is not JSON
  }
  return new Error(message);
}

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch(`${API_URL}/jobs`, { cache: "no-store" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function fetchJob(id: string): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${id}`, { cache: "no-store" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function fetchJobClips(jobId: string): Promise<Clip[]> {
  const res = await fetch(`${API_URL}/jobs/${jobId}/clips`, { cache: "no-store" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function fetchClip(id: string): Promise<Clip> {
  const res = await fetch(`${API_URL}/clips/${id}`, { cache: "no-store" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function submitJob(input: SubmitJobInput): Promise<JobCreated> {
  const form = new FormData();
  if (input.title) form.append("title", input.title);
  if (input.sourceUrl) form.append("source_url", input.sourceUrl);
  if (input.file) form.append("file", input.file);

  const res = await fetch(`${API_URL}/jobs/process`, { method: "POST", body: form });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}