import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import MemoryInspectorPage from "../app/memory-inspector/page";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const memory = {
  creator_id: "creator-7",
  brand_voice: "bold",
  historical_insights: {
    tiktok: ["fast pacing"],
    youtube: ["hook in first 3s"],
  },
  ab_test_history: [{ winning_variant_id: "v2", learned_insight: "question hooks win" }],
};

const agentMemory = { agent_id: "agent-1", memory };

const chatHistory = {
  messages: [
    { role: "user", text: "Always use bold captions", fingerprint: null },
    { role: "mind", text: "I'll remember that always use bold captions", fingerprint: null },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MemoryInspectorPage", () => {
  it("renders the agent tag and insight cards from memory", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/chat/history")) return jsonResponse(chatHistory);
        return jsonResponse(agentMemory);
      }),
    );

    render(<MemoryInspectorPage />);

    expect(await screen.findByText("agent-1")).toBeInTheDocument();
    expect(screen.getByText("Brand voice")).toBeInTheDocument();
    expect(screen.getByText("bold")).toBeInTheDocument();
    expect(screen.getByText("Tiktok insight")).toBeInTheDocument();
    expect(screen.getByText("fast pacing")).toBeInTheDocument();
    expect(screen.getByText("A/B insight · v2")).toBeInTheDocument();
    expect(screen.getByText("question hooks win")).toBeInTheDocument();
  });

  it("renders the raw memory context in the JSON tree", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/chat/history")) return jsonResponse(chatHistory);
        return jsonResponse(agentMemory);
      }),
    );

    render(<MemoryInspectorPage />);

    expect(await screen.findByText(JSON.stringify("creator_id"))).toBeInTheDocument();
    expect(screen.getByText(JSON.stringify("creator-7"))).toBeInTheDocument();
  });

  it("re-fetches memory when the refresh button is clicked", async () => {
    const user = userEvent.setup();
    let memoryCallCount = 0;
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/chat/history")) return jsonResponse(chatHistory);
      if (url.includes("/chat/trends/weekly-status"))
        return jsonResponse({ last_run: null, paused: false, next_run: null });
      memoryCallCount++;
      if (memoryCallCount === 2) return jsonResponse({ ...agentMemory, agent_id: "agent-2" });
      return jsonResponse(agentMemory);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryInspectorPage />);
    await screen.findByText("agent-1");

    await user.click(screen.getByRole("button", { name: /refresh/i }));

    expect(await screen.findByText("agent-2")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("shows a clear error when the memory fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/chat/history")) return jsonResponse(chatHistory);
        return jsonResponse({ detail: "builder api down" }, 502);
      }),
    );

    render(<MemoryInspectorPage />);

    expect(await screen.findByText("builder api down")).toBeInTheDocument();
  });

  it("writes a key/value to memory and reflects it after re-fetch", async () => {
    const user = userEvent.setup();
    const updatedMemory = {
      agent_id: "agent-1",
      memory: { ...memory, tiktok_best_pacing: { ctr: 0.03 } },
    };
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/chat/history")) return jsonResponse(chatHistory);
      if (url.includes("/agent/memory/update")) {
        return jsonResponse({ success: true });
      }
      return jsonResponse(updatedMemory);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryInspectorPage />);
    await screen.findByText("Brand voice");

    await user.type(screen.getByLabelText(/key/i), "tiktok_best_pacing");
    await user.click(screen.getByLabelText(/value/i));
    await user.paste('{"ctr": 0.03}');
    await user.click(screen.getByRole("button", { name: /write to memory/i }));

    expect(await screen.findByText(/Saved.*tiktok_best_pacing/)).toBeInTheDocument();
    expect(await screen.findByText(JSON.stringify("tiktok_best_pacing"))).toBeInTheDocument();

    const postCall = fetchMock.mock.calls.find(
      (call: unknown[]) => call[0] === "http://localhost:8000/api/v1/agent/memory/update",
    );
    expect(postCall).toBeDefined();
    expect(postCall![1].method).toBe("POST");
    expect(postCall![1].body).toBe(JSON.stringify({ key: "tiktok_best_pacing", value: { ctr: 0.03 } }));
  });

  it("shows the update error when the write fails", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/chat/history")) return jsonResponse(chatHistory);
      if (url.includes("/agent/memory/update")) {
        return jsonResponse({ detail: "request failed: timeout" }, 502);
      }
      return jsonResponse(agentMemory);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryInspectorPage />);
    await screen.findByText("Brand voice");

    await user.type(screen.getByLabelText(/key/i), "k");
    await user.type(screen.getByLabelText(/value/i), "v");
    await user.click(screen.getByRole("button", { name: /write to memory/i }));

    expect(await screen.findByText("request failed: timeout")).toBeInTheDocument();
  });

  it("shows an empty state when no learned rules exist", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/chat/history")) return jsonResponse(chatHistory);
        return jsonResponse({ agent_id: "agent-1", memory: {} });
      }),
    );

    render(<MemoryInspectorPage />);

    expect(await screen.findByText(/no learned rules yet/i)).toBeInTheDocument();
  });

  it("renders the Mind's View section with conversation history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/chat/history")) return jsonResponse(chatHistory);
        return jsonResponse(agentMemory);
      }),
    );

    render(<MemoryInspectorPage />);

    expect(await screen.findByText("Mind's View")).toBeInTheDocument();
    expect(screen.getByText("Always use bold captions")).toBeInTheDocument();
    expect(screen.getByText("I'll remember that always use bold captions")).toBeInTheDocument();
  });
});
