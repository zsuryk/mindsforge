import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersistenceCard } from "./persistence-card";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubMemoryFetch(memory: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(jsonResponse({ agent_id: "agent-1", memory }))),
  );
}

function memoryFixture(): Record<string, unknown> {
  const threeDaysAgo = new Date(Date.now() - 3 * 24 * 3600_000).toISOString();
  const tenDaysAgo = new Date(Date.now() - 10 * 24 * 3600_000).toISOString();
  return {
    brand_voice: "Bold, direct, and generous with practical value.",
    brand_rules: [
      { text: "always use bold captions", created_at: tenDaysAgo },
      { text: "never clickbait", created_at: threeDaysAgo },
    ],
    ab_test_history: [
      {
        winning_variant_id: "v2",
        learned_insight: "question hooks win on shorts",
        concluded_at: threeDaysAgo,
      },
    ],
    trend_research: [
      { query: "ai video editing trends", researched_at: tenDaysAgo },
      { query: "hook retention 2026", researched_at: threeDaysAgo },
    ],
  };
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("PersistenceCard", () => {
  it("renders brand voice, rules, insights, and trend queries with ages", async () => {
    stubMemoryFetch(memoryFixture());

    render(<PersistenceCard />);

    expect(await screen.findByTestId("recap-brand-voice")).toHaveTextContent(
      "Bold, direct, and generous",
    );
    expect(screen.getAllByTestId("recap-brand-rule")[0]).toHaveTextContent(
      "never clickbait",
    );
    expect(screen.getAllByTestId("recap-brand-rule")[1]).toHaveTextContent(
      "always use bold captions",
    );
    expect(screen.getByTestId("recap-insight")).toHaveTextContent(
      "question hooks win on shorts",
    );
    expect(screen.getAllByTestId("recap-trend")[0]).toHaveTextContent(
      "hook retention 2026",
    );
    expect(screen.getAllByTestId("recap-trend")[1]).toHaveTextContent(
      "ai video editing trends",
    );

    expect(screen.getAllByText("3d ago")).toHaveLength(3);
    expect(screen.getAllByText("10d ago")).toHaveLength(2);
  });

  it("renders honest empty states for an empty memory", async () => {
    stubMemoryFetch({});

    render(<PersistenceCard />);

    expect(await screen.findByText(/no brand voice yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no brand rules yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no learned insights yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no trend research yet/i)).toBeInTheDocument();
  });

  it("links to the memory inspector", async () => {
    stubMemoryFetch({});

    render(<PersistenceCard />);
    await screen.findByText(/no brand voice yet/i);

    const link = screen.getByRole("link", { name: /see full memory/i });
    expect(link).toHaveAttribute("href", "/memory-inspector");
  });

  it("shows an unavailable state when the memory fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({ detail: "Minds is not configured" }, 503),
        ),
      ),
    );

    render(<PersistenceCard />);

    expect(await screen.findByText(/memory is unavailable/i)).toBeInTheDocument();
    expect(screen.queryByTestId("recap-brand-voice")).not.toBeInTheDocument();
  });

  it("truncates a long brand voice to an excerpt", async () => {
    stubMemoryFetch({ brand_voice: "x".repeat(200) });

    render(<PersistenceCard />);

    const row = await screen.findByTestId("recap-brand-voice");
    expect(row.textContent).toMatch(/^x{120}…$/);
  });

  it("polls for memory changes and re-renders the recap", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ agent_id: "agent-1", memory: {} }))
      .mockResolvedValueOnce(
        jsonResponse({ agent_id: "agent-1", memory: { brand_voice: "bold" } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<PersistenceCard />);
    await act(async () => {});
    expect(screen.getByText(/no brand voice yet/i)).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByTestId("recap-brand-voice")).toHaveTextContent("bold");
  });
});