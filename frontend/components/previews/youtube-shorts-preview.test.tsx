import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import YouTubeShortsPreview from "./youtube-shorts-preview";

function makeAssets() {
  return {
    thumbnail_variants: [
      {
        id: "thumb_1",
        frame_timestamp: 1.0,
        overlay_text: "Wait for it",
        file_path: "/tmp/thumb_1.png",
        url: "/media/adaptations/adapt-1/thumb_1.png",
      },
      {
        id: "thumb_2",
        frame_timestamp: 2.0,
        overlay_text: "The reveal",
        file_path: "/tmp/thumb_2.png",
        url: "/media/adaptations/adapt-1/thumb_2.png",
      },
      {
        id: "thumb_3",
        frame_timestamp: 3.0,
        overlay_text: "You won't believe",
        file_path: "/tmp/thumb_3.png",
        url: "/media/adaptations/adapt-1/thumb_3.png",
      },
    ],
    captions_url: null,
    chapters_url: null,
  };
}

describe("YouTubeShortsPreview", () => {
  it("renders thumbnail variants when assets exist", () => {
    render(
      <YouTubeShortsPreview
        thumbnailBriefs={null}
        platformHooks={null}
        assets={makeAssets()}
      />,
    );

    expect(screen.getByAltText("Thumbnail: Wait for it")).toHaveAttribute(
      "src",
      "http://localhost:8000/media/adaptations/adapt-1/thumb_1.png",
    );
    expect(screen.getByAltText("Thumbnail: The reveal")).toBeInTheDocument();
    expect(screen.getByAltText("Thumbnail: You won't believe")).toBeInTheDocument();
    expect(screen.getByText("Wait for it")).toBeInTheDocument();
    expect(screen.getByText("The reveal")).toBeInTheDocument();
    expect(screen.getByText("You won't believe")).toBeInTheDocument();
  });

  it("renders hook fallback when no adaptation exists", () => {
    render(
      <YouTubeShortsPreview
        thumbnailBriefs={null}
        platformHooks={["Wait for the twist", "This changed everything"]}
        assets={null}
      />,
    );

    expect(screen.getByText("Wait for the twist")).toBeInTheDocument();
    expect(screen.getByText("This changed everything")).toBeInTheDocument();
    expect(screen.getByText("YouTube Shorts")).toBeInTheDocument();
  });

  it("renders empty state when no hooks and no assets", () => {
    render(
      <YouTubeShortsPreview thumbnailBriefs={null} platformHooks={[]} assets={null} />,
    );

    expect(screen.getByText("No Shorts preview available yet.")).toBeInTheDocument();
  });

  it("copies hook text to clipboard on click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(
      <YouTubeShortsPreview
        thumbnailBriefs={null}
        platformHooks={["Wait for the twist"]}
        assets={null}
      />,
    );

    const copyButton = screen.getByRole("button", { name: /copy hook/i });
    await user.click(copyButton);

    expect(writeText).toHaveBeenCalledWith("Wait for the twist");
  });

  it("displays YouTube Shorts label on thumbnail cards", () => {
    render(
      <YouTubeShortsPreview
        thumbnailBriefs={null}
        platformHooks={null}
        assets={makeAssets()}
      />,
    );

    const labels = screen.getAllByText("YouTube Shorts");
    expect(labels.length).toBeGreaterThanOrEqual(1);
  });
});
