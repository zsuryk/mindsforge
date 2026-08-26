import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TikTokPreview from "./tiktok-preview";

describe("TikTokPreview", () => {
  it("renders overlays at placement positions", () => {
    render(
      <TikTokPreview
        overlaySpec={[
          { text: "Top text", placement: "top", style: "bold" },
          { text: "Center text", placement: "center", style: "outlined" },
          { text: "Bottom text", placement: "bottom", style: "italic" },
        ]}
        captionStyle={null}
        stickers={null}
        pinnedComment={null}
        platformHooks={null}
      />,
    );

    expect(screen.getByText("Top text")).toBeInTheDocument();
    expect(screen.getByText("Center text")).toBeInTheDocument();
    expect(screen.getByText("Bottom text")).toBeInTheDocument();
    expect(screen.getByText("TikTok")).toBeInTheDocument();
  });

  it("renders stickers at placement positions", () => {
    render(
      <TikTokPreview
        overlaySpec={null}
        captionStyle={null}
        stickers={[
          { emoji: "🔥", placement: "top-right" },
          { emoji: "✨", placement: "bottom-left" },
        ]}
        pinnedComment={null}
        platformHooks={null}
      />,
    );

    expect(screen.getByRole("img", { name: "Sticker: 🔥" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Sticker: ✨" })).toBeInTheDocument();
  });

  it("renders pinned comment as chat bubble below frame", () => {
    render(
      <TikTokPreview
        overlaySpec={null}
        captionStyle={null}
        stickers={null}
        pinnedComment="First! 🔥"
        platformHooks={null}
      />,
    );

    expect(screen.getByText("Pinned comment")).toBeInTheDocument();
    expect(screen.getByText("First! 🔥")).toBeInTheDocument();
  });

  it("renders caption style below the frame", () => {
    render(
      <TikTokPreview
        overlaySpec={null}
        captionStyle="bold white text with shadow"
        stickers={null}
        pinnedComment={null}
        platformHooks={null}
      />,
    );

    expect(screen.getByText("Caption:")).toBeInTheDocument();
    expect(screen.getByText("bold white text with shadow")).toBeInTheDocument();
  });

  it("renders fallback with hooks when no features exist", () => {
    render(
      <TikTokPreview
        overlaySpec={null}
        captionStyle={null}
        stickers={null}
        pinnedComment={null}
        platformHooks={["POV: you almost scrolled past", "Wait for it"]}
      />,
    );

    expect(screen.getByText("POV: you almost scrolled past")).toBeInTheDocument();
    expect(screen.getByText("Wait for it")).toBeInTheDocument();
    expect(screen.getByText("TikTok")).toBeInTheDocument();
  });

  it("renders empty state when no hooks and no features", () => {
    render(
      <TikTokPreview
        overlaySpec={null}
        captionStyle={null}
        stickers={null}
        pinnedComment={null}
        platformHooks={[]}
      />,
    );

    expect(screen.getByText("No TikTok preview available yet.")).toBeInTheDocument();
  });

  it("renders full preview when features exist even with hooks", () => {
    render(
      <TikTokPreview
        overlaySpec={[{ text: "Overlay", placement: "top", style: "bold" }]}
        captionStyle={null}
        stickers={null}
        pinnedComment={null}
        platformHooks={["Hook text"]}
      />,
    );

    expect(screen.getByText("Overlay")).toBeInTheDocument();
    expect(screen.queryByText("Hook text")).not.toBeInTheDocument();
  });

  it("copies overlay text to clipboard on click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(
      <TikTokPreview
        overlaySpec={[{ text: "Copy me", placement: "top", style: "bold" }]}
        captionStyle={null}
        stickers={null}
        pinnedComment={null}
        platformHooks={null}
      />,
    );

    await user.click(screen.getByRole("button", { name: /copy: Copy me/i }));

    expect(writeText).toHaveBeenCalledWith("Copy me");
  });

  it("copies pinned comment to clipboard on click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(
      <TikTokPreview
        overlaySpec={null}
        captionStyle={null}
        stickers={null}
        pinnedComment="Pinned!"
        platformHooks={null}
      />,
    );

    await user.click(screen.getByRole("button", { name: /copy: Pinned!/i }));

    expect(writeText).toHaveBeenCalledWith("Pinned!");
  });
});
