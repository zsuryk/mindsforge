import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import YouTubeLongFormPreview from "./youtube-longform-preview";

const sampleChapters = [
  { title: "Introduction", timestamp: 0 },
  { title: "The hook", timestamp: 12.5 },
  { title: "Main content", timestamp: 45 },
];

const samplePoll = {
  question: "Which ending is better?",
  options: ["Ending A", "Ending B", "Ending C"],
};

const sampleQuiz = [
  { question: "What changed?", answer: "Everything" },
  { question: "When did it happen?", answer: "At the climax" },
];

describe("YouTubeLongFormPreview", () => {
  it("renders fallback when no features exist", () => {
    render(
      <YouTubeLongFormPreview
        chapters={null}
        poll={null}
        quiz={null}
        thumbnailBriefs={null}
        shortsLink={null}
      />,
    );

    expect(screen.getByText("Generate adaptation to preview")).toBeInTheDocument();
  });

  it("renders poll card with question and options", () => {
    render(
      <YouTubeLongFormPreview
        chapters={null}
        poll={samplePoll}
        quiz={null}
        thumbnailBriefs={null}
        shortsLink={null}
      />,
    );

    expect(screen.getByText("Which ending is better?")).toBeInTheDocument();
    expect(screen.getByText("Ending A")).toBeInTheDocument();
    expect(screen.getByText("Ending B")).toBeInTheDocument();
    expect(screen.getByText("Ending C")).toBeInTheDocument();
    expect(screen.getByText("Poll")).toBeInTheDocument();
  });

  it("renders quiz card with questions and answers", () => {
    render(
      <YouTubeLongFormPreview
        chapters={null}
        poll={null}
        quiz={sampleQuiz}
        thumbnailBriefs={null}
        shortsLink={null}
      />,
    );

    expect(screen.getByText("What changed?")).toBeInTheDocument();
    expect(screen.getByText("Everything")).toBeInTheDocument();
    expect(screen.getByText("When did it happen?")).toBeInTheDocument();
    expect(screen.getByText("At the climax")).toBeInTheDocument();
    expect(screen.getByText("Quiz")).toBeInTheDocument();
  });

  it("renders chapters list with formatted timestamps", () => {
    render(
      <YouTubeLongFormPreview
        chapters={sampleChapters}
        poll={null}
        quiz={null}
        thumbnailBriefs={null}
        shortsLink={null}
      />,
    );

    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("The hook")).toBeInTheDocument();
    expect(screen.getByText("Main content")).toBeInTheDocument();
    expect(screen.getByText("0:00")).toBeInTheDocument();
    expect(screen.getByText("0:12")).toBeInTheDocument();
    expect(screen.getByText("0:45")).toBeInTheDocument();
    expect(screen.getByText("Chapters")).toBeInTheDocument();
  });

  it("renders shorts link badge", () => {
    render(
      <YouTubeLongFormPreview
        chapters={null}
        poll={null}
        quiz={null}
        thumbnailBriefs={null}
        shortsLink="Why I left YouTube"
      />,
    );

    expect(screen.getByText("Related Short:")).toBeInTheDocument();
    expect(screen.getByText("Why I left YouTube")).toBeInTheDocument();
  });

  it("renders all features together", () => {
    render(
      <YouTubeLongFormPreview
        chapters={sampleChapters}
        poll={samplePoll}
        quiz={sampleQuiz}
        thumbnailBriefs={null}
        shortsLink="Related Short"
      />,
    );

    expect(screen.getByText("Which ending is better?")).toBeInTheDocument();
    expect(screen.getByText("What changed?")).toBeInTheDocument();
    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("Related Short:")).toBeInTheDocument();
  });

  it("displays YouTube Video label", () => {
    render(
      <YouTubeLongFormPreview
        chapters={null}
        poll={samplePoll}
        quiz={null}
        thumbnailBriefs={null}
        shortsLink={null}
      />,
    );

    expect(screen.getByText("YouTube Video")).toBeInTheDocument();
  });

  it("copies poll question to clipboard on click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(
      <YouTubeLongFormPreview
        chapters={null}
        poll={samplePoll}
        quiz={null}
        thumbnailBriefs={null}
        shortsLink={null}
      />,
    );

    const copyButton = screen.getByRole("button", { name: /copy: which ending is better/i });
    await user.click(copyButton);

    expect(writeText).toHaveBeenCalledWith("Which ending is better?");
  });

  it("copies chapter title to clipboard on click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(
      <YouTubeLongFormPreview
        chapters={sampleChapters}
        poll={null}
        quiz={null}
        thumbnailBriefs={null}
        shortsLink={null}
      />,
    );

    const copyButton = screen.getByRole("button", { name: /copy: the hook/i });
    await user.click(copyButton);

    expect(writeText).toHaveBeenCalledWith("The hook");
  });

  it("renders empty state when chapters array is empty", () => {
    render(
      <YouTubeLongFormPreview
        chapters={[]}
        poll={null}
        quiz={null}
        thumbnailBriefs={null}
        shortsLink={null}
      />,
    );

    expect(screen.getByText("Generate adaptation to preview")).toBeInTheDocument();
  });
});
