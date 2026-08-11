import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ClipStudioPage from "../app/clips/[id]/page";
import { Clip } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeScoredClip(): Clip {
  return {
    id: "clip-1",
    job_id: "job-1",
    title: "The big reveal",
    start_time: 12.5,
    end_time: 42.0,
    transcript_text: "And here is the moment everyone has been waiting for.",
    video_url: "/media/clips/job-1/clip-1.mp4",
    thumbnail_url: "/media/clips/job-1/clip-1.png",
    virality_score: 78,
    suggested_hooks: {
      virality_score: 78,
      suggested_titles: ["The reveal you missed", "Why nobody talks about this", "Watch until the end"],
      platform_hooks: {
        youtube_shorts: ["Wait for the twist", "This changed everything"],
        tiktok: ["POV: you almost scrolled past", "Nobody told you this"],
        x: ["Hot take:", "Unpopular opinion:"],
      },
    },
    created_at: "2026-08-11T10:00:00Z",
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ClipStudioPage", () => {
  it("shows the loading state then the player and verdict", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(makeScoredClip())));

    const { container } = render(<ClipStudioPage params={{ id: "clip-1" }} />);

    expect(screen.getByText("Loading clip…")).toBeInTheDocument();

    expect(await screen.findByText("The big reveal")).toBeInTheDocument();
    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    expect(video).toHaveAttribute("src", "http://localhost:8000/media/clips/job-1/clip-1.mp4");
    expect(video).toHaveAttribute("poster", "http://localhost:8000/media/clips/job-1/clip-1.png");
    expect(screen.getByText("78")).toBeInTheDocument();
    expect(screen.getByText("High potential — ready to launch")).toBeInTheDocument();
  });

  it("renders a real scored clip with distinct per-platform hooks in tabs", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(makeScoredClip())));

    render(<ClipStudioPage params={{ id: "clip-1" }} />);

    const hooksCard = await screen.findByRole("heading", { name: /platform hooks/i });
    const card = hooksCard.closest("div") as HTMLElement;

    expect(within(card).getByText("Wait for the twist")).toBeInTheDocument();

    await user.click(within(card).getByRole("button", { name: "TikTok" }));
    expect(within(card).getByText("POV: you almost scrolled past")).toBeInTheDocument();
    expect(within(card).queryByText("Wait for the twist")).not.toBeInTheDocument();

    await user.click(within(card).getByRole("button", { name: "X" }));
    expect(within(card).getByText("Hot take:")).toBeInTheDocument();
  });

  it("opens the launch A/B test modal with suggested titles as variants", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(makeScoredClip())));

    render(<ClipStudioPage params={{ id: "clip-1" }} />);

    await user.click(await screen.findByRole("button", { name: /launch a\/b test/i }));

    const dialog = screen.getByRole("dialog", { name: "Launch A/B test" });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("The reveal you missed")).toBeInTheDocument();
    expect(within(dialog).getByText("Why nobody talks about this")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Launch" }));
    expect(
      within(dialog).getByText(/next milestone \(ticket 07\)/i),
    ).toBeInTheDocument();
  });

  it("shows a pending state for unscored clips", async () => {
    const unscored: Clip = { ...makeScoredClip(), virality_score: null, suggested_hooks: null };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(unscored)));

    render(<ClipStudioPage params={{ id: "clip-1" }} />);

    expect(await screen.findByText(/no hooks yet/i)).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
