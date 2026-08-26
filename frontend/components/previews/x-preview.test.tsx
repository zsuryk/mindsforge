import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import XPreview from "./x-preview";

describe("XPreview", () => {
  it("renders caption and hashtags when features exist", () => {
    render(
      <XPreview
        caption="Hot take: this is a great thread"
        hashtags={["hot", "take", "thread"]}
        platformHooks={null}
      />,
    );

    expect(screen.getByText("Hot take: this is a great thread")).toBeInTheDocument();
    expect(screen.getByText("hot")).toBeInTheDocument();
    expect(screen.getByText("take")).toBeInTheDocument();
    expect(screen.getByText("thread")).toBeInTheDocument();
    expect(screen.getByText("X")).toBeInTheDocument();
  });

  it("renders character count for caption", () => {
    render(
      <XPreview caption="Hello world" hashtags={null} platformHooks={null} />,
    );

    expect(screen.getByText("Character count")).toBeInTheDocument();
    const countSpan = document.querySelector(".tabular-nums");
    expect(countSpan).toHaveTextContent("11/280");
  });

  it("renders character count as red when over 90%", () => {
    const longCaption = "a".repeat(260);
    render(
      <XPreview caption={longCaption} hashtags={null} platformHooks={null} />,
    );

    const countSpan = document.querySelector(".tabular-nums");
    expect(countSpan).toHaveTextContent("260/280");
    expect(countSpan).toHaveClass("text-red-500");
  });

  it("renders hashtags as pill badges", () => {
    render(
      <XPreview
        caption={null}
        hashtags={["coding", "dev"]}
        platformHooks={null}
      />,
    );

    expect(screen.getByText("coding")).toBeInTheDocument();
    expect(screen.getByText("dev")).toBeInTheDocument();
  });

  it("renders fallback with hooks when no features exist", () => {
    render(
      <XPreview
        caption={null}
        hashtags={null}
        platformHooks={["Thread starter", "Hot take incoming"]}
      />,
    );

    expect(screen.getByText("Thread starter")).toBeInTheDocument();
    expect(screen.getByText("Hot take incoming")).toBeInTheDocument();
    expect(screen.getByText("X")).toBeInTheDocument();
  });

  it("renders empty state when no hooks and no features", () => {
    render(
      <XPreview caption={null} hashtags={null} platformHooks={[]} />,
    );

    expect(screen.getByText("Generate adaptation to preview")).toBeInTheDocument();
  });

  it("renders full preview when features exist even with hooks", () => {
    render(
      <XPreview
        caption="My post"
        hashtags={["tag"]}
        platformHooks={["Hook text"]}
      />,
    );

    expect(screen.getByText("My post")).toBeInTheDocument();
    expect(screen.queryByText("Hook text")).not.toBeInTheDocument();
  });

  it("copies caption to clipboard on click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(
      <XPreview caption="Copy me" hashtags={null} platformHooks={null} />,
    );

    await user.click(screen.getByRole("button", { name: /copy: Copy me/i }));

    expect(writeText).toHaveBeenCalledWith("Copy me");
  });

  it("copies individual hashtag to clipboard on click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(
      <XPreview caption={null} hashtags={["coding"]} platformHooks={null} />,
    );

    await user.click(screen.getByRole("button", { name: /copy: #coding/i }));

    expect(writeText).toHaveBeenCalledWith("#coding");
  });

  it("renders caption only without hashtags", () => {
    render(
      <XPreview caption="Just a caption" hashtags={null} platformHooks={null} />,
    );

    expect(screen.getByText("Just a caption")).toBeInTheDocument();
    expect(screen.getByText("Character count")).toBeInTheDocument();
  });

  it("renders hashtags only without caption", () => {
    render(
      <XPreview caption={null} hashtags={["only"]} platformHooks={null} />,
    );

    expect(screen.getByText("only")).toBeInTheDocument();
    expect(screen.getByText("Character count")).toBeInTheDocument();
  });
});
