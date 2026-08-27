import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useTodoUnreadCount } from "./use-todo-unread-count";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockReset();
});

describe("useTodoUnreadCount", () => {
  it("returns count of 0 on mount", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ count: 0 }) });
    const { result } = renderHook(() => useTodoUnreadCount());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.count).toBe(0);
  });

  it("fetches and returns the unread count", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ count: 5 }) });
    const { result } = renderHook(() => useTodoUnreadCount());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.count).toBe(5);
  });

  it("sets error when fetch fails", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });
    const { result } = renderHook(() => useTodoUnreadCount());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).toBe("Failed to load unread count");
  });

  it("calls the correct endpoint", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ count: 0 }) });
    renderHook(() => useTodoUnreadCount());

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/todos/unread-count"),
      expect.any(Object),
    );
  });
});
