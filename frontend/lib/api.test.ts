import { afterEach, describe, expect, it, vi } from "vitest";

import {
  deleteJob,
  fetchAbExperiments,
  fetchAgentMemory,
  fetchClip,
  fetchDashboardStats,
  fetchJob,
  fetchJobClips,
  fetchJobs,
  mediaUrl,
  retryJob,
  startAbTest,
  submitJob,
  updateAgentMemory,
} from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchJobs", () => {
  it("returns the job list from GET /jobs", async () => {
    const jobs = [
      {
        id: "abc",
        title: "Video one",
        source_url: "https://example.com/one.mp4",
        file_path: null,
        status: "PENDING",
        duration_seconds: null,
        error_message: null,
        transcript_segments: null,
        created_at: "2026-08-11T10:00:00Z",
        updated_at: "2026-08-11T10:00:00Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(jobs));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchJobs();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/jobs",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(result).toEqual(jobs);
  });
});

describe("fetchJob", () => {
  it("returns a job from GET /jobs/{id}", async () => {
    const job = {
      id: "abc",
      title: "Video one",
      source_url: "https://example.com/one.mp4",
      file_path: null,
      status: "PENDING",
      duration_seconds: null,
      error_message: null,
      transcript_segments: null,
      created_at: "2026-08-11T10:00:00Z",
      updated_at: "2026-08-11T10:00:00Z",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(job)));

    const result = await fetchJob("abc");

    expect(result).toEqual(job);
  });
});

describe("submitJob", () => {  it("posts a source url as form data and returns the created job", async () => {
    const created = { job_id: "abc", status: "PENDING", message: "Job abc accepted" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(created, 202));
    vi.stubGlobal("fetch", fetchMock);

    const result = await submitJob({ title: "My video", sourceUrl: "https://example.com/v.mp4" });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/jobs/process");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect(form.get("title")).toBe("My video");
    expect(form.get("source_url")).toBe("https://example.com/v.mp4");
    expect(form.get("file")).toBeNull();
    expect(result).toEqual(created);
  });

  it("attaches an uploaded file when provided", async () => {
    const created = { job_id: "def", status: "PENDING", message: "Job def accepted" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(created, 202));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["bytes"], "clip.mp4", { type: "video/mp4" });

    await submitJob({ title: "Clip", file });

    const form = fetchMock.mock.calls[0][1].body as FormData;
    expect(form.get("file")).toEqual(file);
    expect(form.get("source_url")).toBeNull();
  });

  it("throws the backend detail message on error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "A job for this URL is already being processed" }, 409)),
    );

    await expect(submitJob({ sourceUrl: "https://example.com/v.mp4" })).rejects.toThrow(
      "A job for this URL is already being processed",
    );
  });
});

function clipFromBackend() {
  return {
    id: "clip-1",
    job_id: "job-1",
    title: "Best moment",
    start_time: 0,
    end_time: 3,
    transcript_text: "hello world.",
    video_url: "/media/clips/job-1/clip-1.mp4",
    thumbnail_url: "/media/clips/job-1/clip-1.png",
    virality_score: null,
    suggested_hooks: null,
    created_at: "2026-08-11T10:00:00Z",
  };
}

describe("fetchJobClips", () => {
  it("returns clips for a job from GET /jobs/{id}/clips", async () => {
    const clips = [clipFromBackend()];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(clips));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchJobClips("job-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/jobs/job-1/clips",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(result).toEqual(clips);
  });
});

describe("fetchClip", () => {
  it("returns a clip from GET /clips/{id}", async () => {
    const clip = clipFromBackend();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(clip)));

    const result = await fetchClip("clip-1");

    expect(result).toEqual(clip);
  });
});

describe("mediaUrl", () => {
  it("prefixes relative media paths with the API origin", () => {
    expect(mediaUrl("/media/clips/job-1/clip-1.mp4")).toBe(
      "http://localhost:8000/media/clips/job-1/clip-1.mp4",
    );
  });

  it("passes through absolute URLs unchanged", () => {
    expect(mediaUrl("https://cdn.example.com/clip.mp4")).toBe("https://cdn.example.com/clip.mp4");
  });
});

describe("fetchAgentMemory", () => {
  it("returns agent id and memory tree from GET /agent/memory", async () => {
    const payload = {
      agent_id: "agent-1",
      memory: { brand_voice: "bold", historical_insights: { tiktok: ["fast pacing"] } },
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchAgentMemory();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agent/memory",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(result).toEqual(payload);
  });

  it("throws the backend detail message on error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "builder api down" }, 502)),
    );

    await expect(fetchAgentMemory()).rejects.toThrow("builder api down");
  });
});

describe("updateAgentMemory", () => {
  it("posts key and value and returns true on success", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await updateAgentMemory("learned_insight", { ctr: 0.03 });

    expect(result).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/agent/memory/update");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ key: "learned_insight", value: { ctr: 0.03 } }));
  });

  it("returns false when the mind does not report success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ success: false })));

    expect(await updateAgentMemory("brand_voice", "warm")).toBe(false);
  });

  it("throws the backend detail message on error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "request failed: timeout" }, 502)),
    );

    await expect(updateAgentMemory("k", "v")).rejects.toThrow("request failed: timeout");
  });
});
describe("startAbTest", () => {
  it("posts clip, platform and titles and returns the created experiment", async () => {
    const created = {
      id: "exp-1",
      clip_id: "clip-1",
      clip_title: "My clip",
      platform: "youtube_shorts",
      status: "ACTIVE",
      variants: [],
      winning_variant_id: null,
      learned_insight: null,
      created_at: "2026-08-11T10:00:00Z",
      concluded_at: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(created, 201));
    vi.stubGlobal("fetch", fetchMock);

    const result = await startAbTest({
      clipId: "clip-1",
      platform: "youtube_shorts",
      titles: ["Title one", "Title two"],
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/ab-tests/start");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(
      JSON.stringify({
        clip_id: "clip-1",
        platform: "youtube_shorts",
        titles: ["Title one", "Title two"],
        variant_kind: "TITLE",
        thumbnail_paths: [],
      }),
    );
    expect(result).toEqual(created);
  });

  it("throws the backend detail message on error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Clip not found" }, 404)),
    );

    await expect(
      startAbTest({ clipId: "nope", platform: "tiktok", titles: ["a", "b"] }),
    ).rejects.toThrow("Clip not found");
  });
});

describe("fetchAbExperiments", () => {
  it("returns experiments and view threshold from GET /ab-tests/active", async () => {
    const experiments = [
      {
        id: "exp-1",
        clip_id: "clip-1",
        clip_title: "My clip",
        platform: "tiktok",
        status: "ACTIVE",
        variants: [],
        winning_variant_id: null,
        learned_insight: null,
        created_at: "2026-08-11T10:00:00Z",
        concluded_at: null,
      },
    ];
    const payload = { view_threshold: 1000, experiments };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchAbExperiments();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/ab-tests/active",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(result).toEqual(payload);
  });
});

describe("fetchDashboardStats", () => {
  it("returns live aggregates from GET /dashboard/stats", async () => {
    const stats = {
      total_clips: 12,
      active_ab_tests: 2,
      avg_virality: 67.5,
      total_insights: 4,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(stats));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchDashboardStats();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/dashboard/stats",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(result).toEqual(stats);
  });

  it("rejects with the backend message when the request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "boom" }, 500)),
    );

    await expect(fetchDashboardStats()).rejects.toThrow("boom");
  });
});

describe("retryJob", () => {
  it("posts to POST /jobs/{id}/retry and returns the re-queued job", async () => {
    const created = { job_id: "abc", status: "PENDING", message: "re-queued" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(created, 202));
    vi.stubGlobal("fetch", fetchMock);

    const result = await retryJob("abc");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/jobs/abc/retry",
      { method: "POST" },
    );
    expect(result).toEqual(created);
  });
});

describe("deleteJob", () => {
  it("sends DELETE /jobs/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteJob("abc");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/jobs/abc",
      { method: "DELETE" },
    );
  });
});
