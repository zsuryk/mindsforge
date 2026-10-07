import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Sidebar } from "./sidebar";

const mockFetch = vi.fn();
const mockUsePathname = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockReset();
  mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ count: 0 }) });
  mockUsePathname.mockReturnValue("/");
});

describe("Sidebar", () => {
  it("renders the Todo nav item", () => {
    render(<Sidebar />);
    expect(screen.getByText("Todo")).toBeInTheDocument();
  });

  it("renders the Todo nav item with Bell icon", () => {
    render(<Sidebar />);
    const todoLink = screen.getByText("Todo").closest("a");
    expect(todoLink).toHaveAttribute("href", "/todo");
  });

  it("shows unread badge when count is greater than zero", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ count: 3 }) });
    render(<Sidebar />);

    await screen.findByText("3");
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("hides unread badge when count is zero", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ count: 0 }) });
    render(<Sidebar />);

    // Wait for loading to finish
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("caps badge at 99+ for counts over 99", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ count: 150 }) });
    render(<Sidebar />);

    await screen.findByText("99+");
    expect(screen.getByText("99+")).toBeInTheDocument();
  });

  it("describes the backend in vendor-neutral terms", () => {
    render(<Sidebar />);

    expect(screen.getByText("OpenAI-compatible LLM")).toBeInTheDocument();
    expect(
      screen.getByText(/any chat completions endpoint, with creator memory stored locally/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/powered by minds/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/animoca/i)).not.toBeInTheDocument();
  });
});
