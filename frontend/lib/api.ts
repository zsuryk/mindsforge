export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

export function mediaUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  const origin = API_URL.replace(/\/api\/v1\/?$/, "");
  return `${origin}${path}`;
}

export type MindsStatus = "ok" | "down" | "unconfigured";

export type HealthStatus = {
  status: "ok" | "degraded" | "down";
  service: string;
  minds: MindsStatus;
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

export async function retryJob(id: string): Promise<JobCreated> {
  const res = await fetch(`${API_URL}/jobs/${id}/retry`, { method: "POST" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function deleteJob(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/jobs/${id}`, { method: "DELETE" });
  if (!res.ok) {
    throw await extractError(res);
  }
}

export type AgentMemory = {
  agent_id: string;
  memory: Record<string, unknown>;
};

export async function fetchAgentMemory(): Promise<AgentMemory> {
  const res = await fetch(`${API_URL}/agent/memory`, { cache: "no-store" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function updateAgentMemory(key: string, value: unknown): Promise<boolean> {
  const res = await fetch(`${API_URL}/agent/memory/update`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, value }),
  });
  if (!res.ok) {
    throw await extractError(res);
  }
  const body = await res.json();
  return body.success === true;
}

export type AbExperimentStatus = "ACTIVE" | "CONCLUDED" | "FAILED";

export type AbExperimentVariantKind = "TITLE" | "THUMBNAIL";

export const AbExperimentVariantKind = {
  TITLE: "TITLE",
  THUMBNAIL: "THUMBNAIL",
} as const;

export type AbVariant = {
  variant_id: string;
  title: string;
  thumbnail_url: string | null;
  ctr: number;
  views: number;
  clicks: number;
};

export type AbExperimentDataSource = "SIMULATED" | "MANUAL";

export type AbExperiment = {
  id: string;
  clip_id: string;
  clip_title: string;
  platform: string;
  variant_kind: AbExperimentVariantKind;
  status: AbExperimentStatus;
  data_source: AbExperimentDataSource;
  variants: AbVariant[];
  winning_variant_id: string | null;
  learned_insight: string | null;
  error_message: string | null;
  created_at: string;
  concluded_at: string | null;
};

export async function startAbTest(input: {
  clipId: string;
  platform: string;
  titles: string[];
  variantKind?: AbExperimentVariantKind;
  thumbnailPaths?: string[];
}): Promise<AbExperiment> {
  const res = await fetch(`${API_URL}/ab-tests/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      clip_id: input.clipId,
      platform: input.platform,
      titles: input.titles,
      variant_kind: input.variantKind ?? "TITLE",
      thumbnail_paths: input.thumbnailPaths ?? [],
    }),
  });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export type AdaptationStatus =
  | "PENDING"
  | "GENERATING"
  | "READY"
  | "FAILED";

export type AdaptationThumbnailVariant = {
  id: string;
  frame_timestamp: number;
  overlay_text: string;
  file_path: string | null;
  url: string;
};

export type AdaptationAssets = {
  thumbnail_variants: AdaptationThumbnailVariant[];
  captions_url: string | null;
  chapters_url: string | null;
};

export type Adaptation = {
  id: string;
  clip_id: string;
  platform: string;
  surface: "SHORTS" | "LONG_FORM" | "POST";
  status: AdaptationStatus;
  features: Record<string, unknown> | null;
  assets: AdaptationAssets | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export async function fetchAdaptations(clipId: string): Promise<Adaptation[]> {
  const res = await fetch(`${API_URL}/clips/${clipId}/adaptations`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function fetchAdaptation(
  clipId: string,
  adaptationId: string,
): Promise<Adaptation> {
  const res = await fetch(`${API_URL}/clips/${clipId}/adaptations/${adaptationId}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function generateAdaptation(
  clipId: string,
  platform: string,
  surface: string,
): Promise<Adaptation> {
  const res = await fetch(
    `${API_URL}/clips/${clipId}/adaptations/${platform}/${surface}`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export type AbActive = {
  view_threshold: number;
  experiments: AbExperiment[];
};

export async function fetchAbExperiments(): Promise<AbActive> {
  const res = await fetch(`${API_URL}/ab-tests/active`, { cache: "no-store" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function updateAbVariantMetrics(
  experimentId: string,
  variantId: string,
  views: number,
  clicks: number,
): Promise<AbExperiment> {
  const res = await fetch(
    `${API_URL}/ab-tests/${experimentId}/variants/${variantId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ views, clicks }),
    },
  );
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export type DashboardStats = {
  total_clips: number;
  active_ab_tests: number;
  avg_virality: number | null;
  total_insights: number;
};

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const res = await fetch(`${API_URL}/dashboard/stats`, { cache: "no-store" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export type MindActivity = {
  id: string;
  event_type: string;
  label: string;
  detail: Record<string, unknown> | null;
  ref_id: string | null;
  created_at: string;
};

export async function fetchMindActivity(limit = 20): Promise<MindActivity[]> {
  const res = await fetch(`${API_URL}/dashboard/activity?limit=${limit}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export type ChatRole = "user" | "mind" | "system";

export type ChatMessage = {
  role: ChatRole;
  text: string;
  fingerprint: string | null;
};

export type ChatSendResult = {
  reply: string;
  rules: string[];
};

export type TrendResult = {
  title: string;
  url: string;
  content: string;
};

export async function fetchChatHistory(): Promise<{ messages: ChatMessage[] }> {
  const res = await fetch(`${API_URL}/chat/history`, { cache: "no-store" });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function sendChatMessage(message: string): Promise<ChatSendResult> {
  const res = await fetch(`${API_URL}/chat/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}

export async function researchTrends(
  query: string,
): Promise<{ results: TrendResult[] }> {
  const res = await fetch(`${API_URL}/chat/trends`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    throw await extractError(res);
  }
  return res.json();
}