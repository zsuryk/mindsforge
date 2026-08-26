import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import PlatformPreviewCanvas from "./platform-preview-canvas";
import { Clip } from "@/lib/api";

function makeClip(overrides?: Partial<Clip>): Clip {
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
      suggested_titles: ["The reveal you missed"],
      platform_hooks: {
        youtube_shorts: ["Wait for the twist", "This changed everything"],
        tiktok: ["POV: you almost scrolled past"],
        x: ["Hot take:"],
      },
    },
    latest_adaptations: [],
    created_at: "2026-08-11T10:00:00Z",
    ...overrides,
  };
}

describe("PlatformPreviewCanvas", () => {
  it("renders the virality gauge with score", () => {
    render(<PlatformPreviewCanvas clip={makeClip()} />);

    expect(screen.getByText("78")).toBeInTheDocument();
    expect(screen.getByText("virality")).toBeInTheDocument();
    expect(screen.getByText("High potential — ready to launch")).toBeInTheDocument();
  });

  it("renders all four platform tabs", () => {
    render(<PlatformPreviewCanvas clip={makeClip()} />);

    expect(screen.getByRole("tab", { name: "YouTube Shorts" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "YouTube Video" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "TikTok" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "X" })).toBeInTheDocument();
  });

  it("shows Shorts fallback with hooks when no adaptation exists", () => {
    render(<PlatformPreviewCanvas clip={makeClip()} />);

    expect(screen.getByText("Wait for the twist")).toBeInTheDocument();
    expect(screen.getByText("This changed everything")).toBeInTheDocument();
  });

  it("shows YouTube Video fallback prompt", async () => {
    const user = userEvent.setup();
    render(<PlatformPreviewCanvas clip={makeClip()} />);

    await user.click(screen.getByRole("tab", { name: "YouTube Video" }));

    expect(screen.getByText("Generate adaptation to preview")).toBeInTheDocument();
  });

  it("shows TikTok fallback with hooks", async () => {
    const user = userEvent.setup();
    render(<PlatformPreviewCanvas clip={makeClip()} />);

    await user.click(screen.getByRole("tab", { name: "TikTok" }));

    expect(screen.getByText("POV: you almost scrolled past")).toBeInTheDocument();
  });

  it("shows X fallback with hooks", async () => {
    const user = userEvent.setup();
    render(<PlatformPreviewCanvas clip={makeClip()} />);

    await user.click(screen.getByRole("tab", { name: "X" }));

    expect(screen.getByText("Hot take:")).toBeInTheDocument();
  });

  it("renders thumbnails when adaptation assets exist", () => {
    const clip = makeClip({
      latest_adaptations: [
        {
          platform: "youtube",
          surface: "SHORTS",
          status: "READY",
          features: null,
          assets: {
            thumbnail_variants: [
              {
                id: "thumb_1",
                frame_timestamp: 1.0,
                overlay_text: "Wait for it",
                file_path: "/tmp/thumb_1.png",
                url: "/media/adaptations/adapt-1/thumb_1.png",
              },
            ],
            captions_url: null,
            chapters_url: null,
          },
        },
      ],
    });

    render(<PlatformPreviewCanvas clip={clip} />);

    expect(screen.getByAltText("Thumbnail: Wait for it")).toBeInTheDocument();
  });

  it("maintains layout stability when switching tabs", async () => {
    const user = userEvent.setup();
    const { container } = render(<PlatformPreviewCanvas clip={makeClip()} />);

    const tabsList = screen.getByRole("tablist");
    const initialHeight = tabsList.getBoundingClientRect().height;

    await user.click(screen.getByRole("tab", { name: "TikTok" }));
    await user.click(screen.getByRole("tab", { name: "YouTube Video" }));
    await user.click(screen.getByRole("tab", { name: "X" }));
    await user.click(screen.getByRole("tab", { name: "YouTube Shorts" }));

    const finalHeight = tabsList.getBoundingClientRect().height;
    expect(finalHeight).toBe(initialHeight);
  });

  it("shows null state when no hooks and no adaptations", () => {
    const clip = makeClip({
      suggested_hooks: null,
      latest_adaptations: [],
    });

    render(<PlatformPreviewCanvas clip={clip} />);

    expect(screen.getByText("No Shorts preview available yet.")).toBeInTheDocument();
  });

  it("renders TikTok overlays and pinned comment when adaptation exists", async () => {
    const user = userEvent.setup();
    const clip = makeClip({
      latest_adaptations: [
        {
          platform: "tiktok",
          surface: "POST",
          status: "READY",
          features: {
            overlay_spec: [{ text: "POV: plot twist", placement: "top", style: "bold" }],
            caption_style: "bold white",
            stickers: [{ emoji: "🔥", placement: "top-right" }],
            pinned_comment: "Part 2?",
          },
          assets: null,
        },
      ],
    });

    render(<PlatformPreviewCanvas clip={clip} />);

    await user.click(screen.getByRole("tab", { name: "TikTok" }));

    expect(screen.getByText("POV: plot twist")).toBeInTheDocument();
    expect(screen.getByText("Part 2?")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Sticker: 🔥" })).toBeInTheDocument();
  });
});
