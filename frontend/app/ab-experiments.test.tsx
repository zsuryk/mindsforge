import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import AbExperimentsPage from "./ab-experiments/page";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function activeExperiment(overrides: Record<string, unknown> = {}) {
  return {
    id: "exp-1",
    clip_id: "clip-1",
    clip_title: "The big reveal",
    platform: "youtube_shorts",
    variant_kind: "TITLE",
    status: "ACTIVE",
    data_source: "SIMULATED",
    winning_variant_id: null,
    learned_insight: null,
    error_message: null,
    created_at: "2026-08-11T10:00:00Z",
    concluded_at: null,
    variants: [
      {
        variant_id: "v1",
        title: "Hook A",
        thumbnail_url: null,
        ctr: 5,
        views: 100,
        clicks: 5,
      },
    ],
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AbExperimentsPage", () => {
  it("renders a simulated badge for simulated experiments and a manual badge for manual ones", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          view_threshold: 1000,
          experiments: [
            activeExperiment({ id: "exp-1", data_source: "SIMULATED" }),
            activeExperiment({ id: "exp-2", data_source: "MANUAL" }),
          ],
        }),
      ),
    );

    render(<AbExperimentsPage />);

    expect(await screen.findByText("simulated")).toBeInTheDocument();
    expect(screen.getByText("manual")).toBeInTheDocument();
  });

  it("edits an ACTIVE variant via the PATCH and shows the updated card with the manual badge", async () => {
    const original = activeExperiment();
    const updated = activeExperiment({
      data_source: "MANUAL",
      variants: [
        {
          variant_id: "v1",
          title: "Hook A",
          thumbnail_url: null,
          ctr: 4,
          views: 250,
          clicks: 10,
        },
      ],
    });
    let patched = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        patched = true;
        return Promise.resolve(jsonResponse(updated));
      }
      return Promise.resolve(
        jsonResponse({
          view_threshold: 1000,
          experiments: [patched ? updated : original],
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<AbExperimentsPage />);

    await user.click(
      await screen.findByRole("button", { name: /edit metrics for hook a/i }),
    );

    const viewsInput = screen.getByLabelText("views for Hook A");
    const clicksInput = screen.getByLabelText("clicks for Hook A");
    await user.clear(viewsInput);
    await user.type(viewsInput, "250");
    await user.clear(clicksInput);
    await user.type(clicksInput, "10");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    const patchCall = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "PATCH",
    );
    expect(patchCall).toBeDefined();
    const [patchUrl, patchInit] = patchCall as [string, RequestInit];
    expect(patchUrl).toBe(
      "http://localhost:8000/api/v1/ab-tests/exp-1/variants/v1",
    );
    expect(JSON.parse(String(patchInit.body))).toEqual({
      views: 250,
      clicks: 10,
    });

    expect(await screen.findByText(/250 views/)).toBeInTheDocument();
    expect(screen.getByText(/10 clicks/)).toBeInTheDocument();
    expect(screen.getByText("manual")).toBeInTheDocument();
  });

  it("shows no edit controls on CONCLUDED and FAILED experiments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          view_threshold: 1000,
          experiments: [
            activeExperiment({
              id: "exp-2",
              status: "CONCLUDED",
              winning_variant_id: "v1",
              learned_insight: "Hook A won",
              concluded_at: "2026-08-19T10:00:00Z",
            }),
            activeExperiment({
              id: "exp-3",
              status: "FAILED",
              error_message: "builder api down",
              concluded_at: "2026-08-19T10:00:00Z",
            }),
          ],
        }),
      ),
    );

    render(<AbExperimentsPage />);

    expect(await screen.findByText(/winner/i)).toBeInTheDocument();
    expect(screen.getByText(/builder api down/i)).toBeInTheDocument();
    expect(
      screen.queryAllByRole("button", { name: /edit/i }),
    ).toHaveLength(0);
  });
});