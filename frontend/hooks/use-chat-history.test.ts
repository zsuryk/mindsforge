import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useChatHistory } from "./use-chat-history";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useChatHistory", () => {
  it("returns messages on successful fetch", async () => {
    const messages = [
      { role: "user", text: "Hello", fingerprint: null },
      { role: "mind", text: "Hi there", fingerprint: null },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ messages })),
    );

    const { result } = renderHook(() => useChatHistory());

    await waitFor(() => {
      expect(result.current.messages).toEqual(messages);
    });
    expect(result.current.error).toBeNull();
  });

  it("returns empty array when no messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ messages: [] })),
    );

    const { result } = renderHook(() => useChatHistory());

    await waitFor(() => {
      expect(result.current.messages).toEqual([]);
    });
    expect(result.current.error).toBeNull();
  });

  it("sets error on fetch failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network")),
    );

    const { result } = renderHook(() => useChatHistory());

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to load chat history");
    });
    expect(result.current.messages).toEqual([]);
  });

  it("sets error on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("error", { status: 500, statusText: "Internal Server Error" }),
      ),
    );

    const { result } = renderHook(() => useChatHistory());

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to load chat history");
    });
  });
});
