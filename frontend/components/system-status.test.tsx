import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SystemStatus } from "./system-status";

const health = {
  status: "ok" as const,
  service: "mindsforge-backend",
  llm: "ok" as const,
  timestamp: "2026-10-07T00:00:00+00:00",
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(health),
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SystemStatus", () => {
  it("reports the backend and the configured LLM backend", async () => {
    render(<SystemStatus />);

    expect(await screen.findByText("Backend online")).toBeInTheDocument();
    expect(screen.getByText("LLM online")).toBeInTheDocument();
  });

  it.each([
    ["down", "LLM offline"],
    ["unconfigured", "LLM unconfigured"],
  ] as const)("labels the %s llm status", async (llm, label) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ ...health, llm }),
      }),
    );

    render(<SystemStatus />);

    expect(await screen.findByText(label)).toBeInTheDocument();
  });

  it("marks the backend offline and the mind unreachable when the health check fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network down")),
    );

    render(<SystemStatus />);

    expect(await screen.findByText("Backend offline")).toBeInTheDocument();
    expect(await screen.findByText("LLM unknown")).toBeInTheDocument();
    expect(screen.queryByText("Checking…")).not.toBeInTheDocument();
  });
});
