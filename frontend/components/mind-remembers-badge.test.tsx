import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MindRemembersBadge from "./mind-remembers-badge";

describe("MindRemembersBadge", () => {
  it("renders nothing when there are no brand rules", () => {
    const { container } = render(
      <MindRemembersBadge messages={[{ role: "user", text: "Hello" }]} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the Mind remembers badge with rule chips", () => {
    const messages = [
      { role: "user", text: "I always use bold captions" },
      { role: "mind", text: "Got it, I'll remember that." },
    ];
    render(<MindRemembersBadge messages={messages} />);

    expect(screen.getByText("Mind remembers")).toBeInTheDocument();
    expect(screen.getByText("I always use bold captions")).toBeInTheDocument();
    expect(screen.getByText("Got it, I'll remember that.")).toBeInTheDocument();
  });

  it("truncates long rule text to 40 characters", () => {
    const longRule = "I always " + "a".repeat(50);
    const messages = [{ role: "user", text: longRule }];
    render(<MindRemembersBadge messages={messages} />);

    const truncatedText = "I always " + "a".repeat(31) + "…";
    expect(screen.getByText(truncatedText)).toBeInTheDocument();
  });

  it("does not truncate short rule text", () => {
    const messages = [{ role: "user", text: "I always use bold" }];
    render(<MindRemembersBadge messages={messages} />);

    expect(screen.getByText("I always use bold")).toBeInTheDocument();
  });
});
