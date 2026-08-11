import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { JsonTree } from "./json-tree";

afterEach(() => {
  cleanup();
});

describe("JsonTree", () => {
  it("renders keys, string, number, boolean and null tokens", () => {
    render(
      <JsonTree
        data={{
          brand_voice: "bold",
          score: 42,
          active: true,
          nothing: null,
        }}
      />,
    );

    expect(screen.getByText(JSON.stringify("brand_voice"))).toBeInTheDocument();
    expect(screen.getByText(JSON.stringify("bold"))).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("true")).toBeInTheDocument();
    expect(screen.getByText("null")).toBeInTheDocument();
  });

  it("opens a closed nested object on click", async () => {
    const user = userEvent.setup();
    render(<JsonTree data={{ outer: { brand_voice: "bold" } }} />);

    const closedToggle = screen.getByRole("button", { expanded: false });
    expect(screen.queryByText(JSON.stringify("bold"))).not.toBeInTheDocument();

    await user.click(closedToggle);

    expect(screen.getByText(JSON.stringify("bold"))).toBeInTheDocument();
  });

  it("collapses the root when it is clicked", async () => {
    const user = userEvent.setup();
    render(<JsonTree data={{ a: { b: "value" } }} />);

    const rootToggle = screen.getByRole("button", { expanded: true });
    await user.click(rootToggle);

    expect(screen.getByRole("button", { expanded: false })).toBeInTheDocument();
    expect(screen.queryByText(JSON.stringify("value"))).not.toBeInTheDocument();
  });

  it("renders nested children after opening each level", async () => {
    const user = userEvent.setup();
    render(<JsonTree data={{ nested: { deep: ["x", "y"] } }} />);

    await user.click(screen.getByRole("button", { expanded: false }));
    expect(screen.getByText(JSON.stringify("deep"))).toBeInTheDocument();

    await user.click(screen.getByRole("button", { expanded: false }));
    expect(screen.getByText(JSON.stringify("x"))).toBeInTheDocument();
    expect(screen.getByText(JSON.stringify("y"))).toBeInTheDocument();
  });
});
