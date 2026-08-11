import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchClip, fetchJob, fetchJobClips, fetchJobs, mediaUrl, submitJob } from "./api";

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