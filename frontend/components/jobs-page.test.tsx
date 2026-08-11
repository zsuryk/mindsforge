import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import JobsPage from "../app/jobs/page";
import { Job } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    title: "My video",
    source_url: "https://example.com/v.mp4",
    file_path: null,
    status: "PENDING",
    duration_seconds: null,
    transcript_segments: null,
    error_message: null,
    created_at: "2026-08-11T10:00:00Z",
    updated_at: "2026-08-11T10:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("JobsPage", () => {
  it("renders the submitted jobs with status badges", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([makeJob()])));

    render(<JobsPage />);

    expect(await screen.findByText("My video")).toBeInTheDocument();
    expect(screen.getByText("PENDING")).toBeInTheDocument();
  });

  it("submits a new job via the url form and refreshes the list", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ job_id: "job-2", status: "PENDING", message: "accepted" }, 202))
      .mockResolvedValueOnce(jsonResponse([makeJob({ id: "job-2", title: "New video" })]));
    vi.stubGlobal("fetch", fetchMock);

    render(<JobsPage />);
    await screen.findByText(/no jobs/i);

    await user.type(screen.getByLabelText(/source url/i), "https://example.com/new.mp4");
    await user.type(screen.getByLabelText(/title/i), "New video");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    const form = fetchMock.mock.calls[1][1].body as FormData;
    expect(form.get("source_url")).toBe("https://example.com/new.mp4");
    expect(form.get("title")).toBe("New video");

    expect(await screen.findByText("New video")).toBeInTheDocument();
  });

  it("shows the backend error message when submission fails", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(
        jsonResponse({ detail: "A job for this URL is already being processed" }, 409),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<JobsPage />);
    await screen.findByText(/no jobs/i);

    await user.type(screen.getByLabelText(/source url/i), "https://example.com/v.mp4");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(
      await screen.findByText("A job for this URL is already being processed"),
    ).toBeInTheDocument();
  });

  it("polls for job state changes and re-renders the badges", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([makeJob()]))
      .mockResolvedValueOnce(jsonResponse([makeJob({ status: "COMPLETED" })]));
    vi.stubGlobal("fetch", fetchMock);

    render(<JobsPage />);
    await act(async () => {});
    expect(screen.getByText("PENDING")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });

  it("shows the pipeline error message for failed jobs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse([
        makeJob({ status: "FAILED", error_message: "network down" }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<JobsPage />);

    expect(await screen.findByText("network down")).toBeInTheDocument();
  });

  it("shows segment count and duration for transcribed jobs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse([
        makeJob({
          status: "TRANSCRIBING",
          transcript_segments: [
            { text: "hello world", start: 0, end: 1.5 },
            { text: "still going", start: 1.5, end: 3 },
          ],
          duration_seconds: 30,
        }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<JobsPage />);

    expect(await screen.findByText(/2 segments/)).toBeInTheDocument();
    expect(screen.getByText(/30.0s/)).toBeInTheDocument();
  });

  it("shows extracted clips with a playable video preview for completed jobs", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([makeJob({ status: "COMPLETED" })]))
      .mockResolvedValueOnce(
        jsonResponse([
          {
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
          },
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<JobsPage />);

    expect(await screen.findByText("Clips ready")).toBeInTheDocument();
    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    expect(video).toHaveAttribute("src", "http://localhost:8000/media/clips/job-1/clip-1.mp4");
    expect(video).toHaveAttribute("poster", "http://localhost:8000/media/clips/job-1/clip-1.png");
    expect(await screen.findByText("Best moment")).toBeInTheDocument();
    expect(screen.getByText("hello world.")).toBeInTheDocument();
  });

  it("does not fetch clips for jobs that are not completed", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([makeJob({ status: "FAILED" })]));
    vi.stubGlobal("fetch", fetchMock);

    render(<JobsPage />);

    await screen.findByText("FAILED");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});