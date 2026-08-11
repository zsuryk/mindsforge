import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../app/page";
import { DashboardStats, Job } from "@/lib/api";

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeStats(overrides: Partial<DashboardStats> = {}): DashboardStats {
  return {
    total_clips: 0,
    active_ab_tests: 0,
    avg_virality: null,
    total_insights: 0,
    ...overrides,
  };
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

function stubFetch(stats: DashboardStats, jobs: Job[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/dashboard/stats")) {
        return Promise.resolve(jsonResponse(stats));
      }
      return Promise.resolve(jsonResponse(jobs));
    }),
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  pushMock.mockReset();
});

describe("DashboardPage", () => {
  it("renders the MindsForge Studio header with live metric values", async () => {
    stubFetch(
      makeStats({ total_clips: 12, active_ab_tests: 2, avg_virality: 67.5, total_insights: 4 }),
      [],
    );

    render(<DashboardPage />);

    expect(await screen.findByText("MindsForge Studio")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("67.5")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders zero-valued cards and an empty-state message when there is no data yet", async () => {
    stubFetch(makeStats(), []);

    render(<DashboardPage />);

    expect(await screen.findByText(/no jobs yet/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/video url/i)).toBeInTheDocument();
    expect(screen.getAllByText("0")).toHaveLength(3);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("submits the pasted URL and navigates to the jobs page", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(makeStats()))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(
        jsonResponse({ job_id: "job-2", status: "PENDING", message: "accepted" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DashboardPage />);
    await screen.findByText(/no jobs yet/i);

    await user.type(screen.getByLabelText(/video url/i), "https://example.com/new.mp4");
    await user.click(screen.getByRole("button", { name: /process/i }));

    const post = fetchMock.mock.calls[2][1].body as FormData;
    expect(post.get("source_url")).toBe("https://example.com/new.mp4");
    expect(pushMock).toHaveBeenCalledWith("/jobs");
  });

  it("shows the backend error when the URL submission fails", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(makeStats()))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(
        jsonResponse({ detail: "A job for this URL is already being processed" }, 409),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DashboardPage />);
    await screen.findByText(/no jobs yet/i);

    await user.type(screen.getByLabelText(/video url/i), "https://example.com/v.mp4");
    await user.click(screen.getByRole("button", { name: /process/i }));

    expect(
      await screen.findByText("A job for this URL is already being processed"),
    ).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("lists recent jobs with animated badges for in-progress statuses", async () => {
    stubFetch(makeStats(), [
      makeJob(),
      makeJob({ id: "job-2", title: "Done video", status: "COMPLETED" }),
    ]);

    render(<DashboardPage />);

    expect(await screen.findByText("My video")).toBeInTheDocument();
    expect(screen.getByText("Done video")).toBeInTheDocument();

    const pendingBadge = screen.getByText("PENDING").closest("span");
    expect(pendingBadge?.querySelector(".animate-pulse")).not.toBeNull();

    const completedBadge = screen.getByText("COMPLETED").closest("span");
    expect(completedBadge?.querySelector(".animate-pulse")).toBeNull();
  });

  it("polls for stats changes and re-renders the metric cards", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(makeStats()))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(makeStats({ total_clips: 7 })))
      .mockResolvedValueOnce(jsonResponse([makeJob()]));
    vi.stubGlobal("fetch", fetchMock);

    render(<DashboardPage />);
    await act(async () => {});
    expect(screen.getAllByText("0")).toHaveLength(3);

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("My video")).toBeInTheDocument();
  });
});
