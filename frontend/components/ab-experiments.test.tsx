import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import AbExperimentsPage from "../app/ab-experiments/page";
import { AbExperiment } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function activeExperiment(): AbExperiment {
  return {
    id: "exp-active",
    clip_id: "clip-1",
    clip_title: "The big reveal",
    platform: "youtube_shorts",
    variant_kind: "TITLE",
    status: "ACTIVE",
    error_message: null,
    variants: [
      {
        variant_id: "v1",
        title: "The reveal you missed",
        thumbnail_url: "/media/clips/job-1/clip-1.png",
        ctr: 3.2,
        views: 420,
      },
      {
        variant_id: "v2",
        title: "Why nobody talks about this",
        thumbnail_url: "/media/clips/job-1/clip-1.png",
        ctr: 1.8,
        views: 380,
      },
    ],
    winning_variant_id: null,
    learned_insight: null,
    created_at: "2026-08-11T10:00:00Z",
    concluded_at: null,
  };
}

function concludedExperiment(): AbExperiment {
  return {
    id: "exp-done",
    clip_id: "clip-2",
    clip_title: "The second reveal",
    platform: "tiktok",
    variant_kind: "TITLE",
    status: "CONCLUDED",
    error_message: null,
    variants: [
      {
        variant_id: "w1",
        title: "POV: you almost scrolled past",
        thumbnail_url: null,
        ctr: 4.8,
        views: 640,
      },
      {
        variant_id: "w2",
        title: "Nobody told you this",
        thumbnail_url: null,
        ctr: 2.1,
        views: 360,
      },
    ],
    winning_variant_id: "w1",
    learned_insight:
      "On TikTok, “POV: you almost scrolled past” won the A/B test after 1,000 total views with a 4.8% click-through rate. Reuse this title formula.",
    created_at: "2026-08-10T10:00:00Z",
    concluded_at: "2026-08-11T09:00:00Z",
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AbExperimentsPage", () => {
  it("shows active variant cards with live view counts and CTR", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ view_threshold: 1000, experiments: [activeExperiment()] })));

    render(<AbExperimentsPage />);

    expect(await screen.findByText("Active tests")).toBeInTheDocument();
    expect(screen.getByText("The big reveal")).toBeInTheDocument();
    expect(screen.getByText("YouTube Shorts · 2 variants")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("The reveal you missed")).toBeInTheDocument();
    expect(screen.getByText(/420 views · 3.20% CTR/)).toBeInTheDocument();
    expect(screen.getByText(/380 views · 1.80% CTR/)).toBeInTheDocument();
    expect(screen.getByText("leading")).toBeInTheDocument();
    expect(screen.getByText("800 / 1,000")).toBeInTheDocument();
    expect(screen.getByText("CTR comparison")).toBeInTheDocument();
    expect(screen.getByText("Concluded")).toBeInTheDocument();
    expect(screen.getByText(/no concluded tests yet/i)).toBeInTheDocument();
  });

  it("renders a highlighted winner banner with the learned insight and CTR chart", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ view_threshold: 1000, experiments: [concludedExperiment()] })),
    );

    render(<AbExperimentsPage />);

    expect(
      await screen.findByText(/Winner · TikTok · The second reveal/),
    ).toBeInTheDocument();
    expect(screen.getByText("POV: you almost scrolled past")).toBeInTheDocument();
    expect(screen.getByText(/640 views · 4.80% CTR/)).toBeInTheDocument();
    expect(
      screen.getByText(/learned insight — written to memory/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/won the A\/B test after 1,000 total views with a 4.8%/),
    ).toBeInTheDocument();
    expect(screen.getByText("CTR comparison")).toBeInTheDocument();
    expect(screen.getByText(/concluded after 1,000 total views/i)).toBeInTheDocument();
  });

  it("shows an empty state when no experiments exist", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ view_threshold: 1000, experiments: [] })));

    render(<AbExperimentsPage />);

    expect(
      await screen.findByText(/no active tests — launch an a\/b test/i),
    ).toBeInTheDocument();
  });

  it("shows a clear error when the fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "backend unreachable" }, 502)),
    );

    render(<AbExperimentsPage />);

    expect(await screen.findByText("backend unreachable")).toBeInTheDocument();
  });

  it("re-fetches experiments when the refresh button is clicked", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ view_threshold: 1000, experiments: [activeExperiment()] }))
      .mockResolvedValueOnce(jsonResponse({ view_threshold: 1000, experiments: [concludedExperiment()] }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AbExperimentsPage />);
    await screen.findByText("The big reveal");

    await user.click(screen.getByRole("button", { name: /refresh/i }));

    expect(
      await screen.findByText(/Winner · TikTok · The second reveal/),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
