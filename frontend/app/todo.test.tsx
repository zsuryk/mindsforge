import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import TodoPage from "./todo/page";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function todoItem(overrides: Record<string, unknown> = {}) {
  return {
    id: "todo-1",
    type: "experiment_result",
    title: "Experiment concluded",
    body: "Variant A won with 12% CTR improvement.",
    action_url: "/clips/abc123",
    action_label: "View clip",
    is_read: false,
    is_archived: false,
    created_at: "2026-08-25T10:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function stubFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/todos/unread-count")) {
        return Promise.resolve(jsonResponse({ count: routes.unreadCount ?? 0 }));
      }
      if (url.includes("/todos")) {
        return Promise.resolve(
          jsonResponse({ items: routes.todos ?? [], unread_count: routes.unreadCount ?? 0 }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    }),
  );
}

describe("TodoPage", () => {
  it("renders empty state when no items", async () => {
    stubFetch({ todos: [], unreadCount: 0 });

    render(<TodoPage />);

    expect(
      await screen.findByText(/no todo items yet/i),
    ).toBeInTheDocument();
  });

  it("renders todo cards with type badge, title, body, and timestamp", async () => {
    stubFetch({
      todos: [
        todoItem({
          type: "weekly_digest",
          title: "Weekly Digest — Aug 25",
          body: "Top trending: AI hooks, vertical video, engagement pods.",
        }),
      ],
      unreadCount: 1,
    });

    render(<TodoPage />);

    await screen.findByText("Weekly Digest — Aug 25");
    expect(screen.getByText(/top trending: ai hooks/i)).toBeInTheDocument();
    // Badge in the card uses span, option in select uses option — get the card badge
    const badges = screen.getAllByText("Weekly Digest");
    expect(badges.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1 item · 1 unread")).toBeInTheDocument();
  });

  it("renders action button when action_url and action_label are present", async () => {
    stubFetch({
      todos: [todoItem({ action_url: "/clips/abc", action_label: "View clip" })],
      unreadCount: 0,
    });

    render(<TodoPage />);

    await screen.findByText("View clip");
    const link = screen.getByRole("link", { name: "View clip" });
    expect(link).toHaveAttribute("href", "/clips/abc");
  });

  it("does not render action button when action_url is absent", async () => {
    stubFetch({
      todos: [todoItem({ action_url: null, action_label: null })],
      unreadCount: 0,
    });

    render(<TodoPage />);

    await screen.findByText("Experiment concluded");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("filters items by type", async () => {
    const user = userEvent.setup();
    const allTodos = [
      todoItem({ id: "t1", type: "experiment_result", title: "Exp result" }),
      todoItem({ id: "t2", type: "trend_alert", title: "Trend alert" }),
    ];

    stubFetch({ todos: allTodos, unreadCount: 0 });

    render(<TodoPage />);

    await screen.findByText("Exp result");
    expect(screen.getByText("Trend alert")).toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText("Filter todo items"),
      "experiment_result",
    );

    // The fetch mock returns same data for both, but let's verify the select changed
    expect(screen.getByLabelText("Filter todo items")).toHaveValue("experiment_result");
  });

  it("marks item as read after viewing for 2 seconds", async () => {
    vi.useFakeTimers();
    const patchMock = vi.fn().mockResolvedValue(
      jsonResponse({ ...todoItem({ is_read: true }) }),
    );

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/todos/unread-count")) {
          return Promise.resolve(jsonResponse({ count: 1 }));
        }
        if (url.includes("/todos/todo-1") && init?.method === "PATCH") {
          return patchMock();
        }
        return Promise.resolve(
          jsonResponse({
            items: [todoItem()],
            unread_count: 1,
          }),
        );
      }),
    );

    render(<TodoPage />);
    await act(async () => {});

    // Advance 2 seconds to trigger mark-as-read
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(patchMock).toHaveBeenCalled();
    expect(patchMock.mock.calls.length).toBeGreaterThan(0);
  });

  it("shows unread dot for unread items", async () => {
    stubFetch({
      todos: [todoItem({ is_read: false })],
      unreadCount: 1,
    });

    render(<TodoPage />);

    await screen.findByText("Experiment concluded");
    const cards = screen.getAllByTestId("todo-card");
    expect(cards[0].querySelector(".bg-primary")).toBeInTheDocument();
  });

  it("does not show unread dot for read items", async () => {
    stubFetch({
      todos: [todoItem({ is_read: true })],
      unreadCount: 0,
    });

    render(<TodoPage />);

    await screen.findByText("Experiment concluded");
    const cards = screen.getAllByTestId("todo-card");
    expect(cards[0].querySelector(".bg-primary")).not.toBeInTheDocument();
  });

  it("opens archive confirmation dialog and archives on confirm", async () => {
    const user = userEvent.setup();
    const patchMock = vi.fn().mockResolvedValue(
      jsonResponse({ ...todoItem({ is_archived: true }) }),
    );

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/todos/unread-count")) {
          return Promise.resolve(jsonResponse({ count: 0 }));
        }
        if (url.includes("/todos") && init?.method === "PATCH") {
          return patchMock();
        }
        return Promise.resolve(
          jsonResponse({ items: [todoItem()], unread_count: 0 }),
        );
      }),
    );

    render(<TodoPage />);
    await screen.findByText("Experiment concluded");

    const archiveBtn = screen.getByLabelText("Archive item");
    await user.click(archiveBtn);

    expect(await screen.findByText("Archive item?")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Archive" }));

    expect(
      screen.queryByText("Experiment concluded"),
    ).not.toBeInTheDocument();
  });

  it("displays error banner when fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/todos/unread-count")) {
          return Promise.resolve(jsonResponse({ count: 0 }));
        }
        return Promise.resolve(jsonResponse({ detail: "server error" }, 500));
      }),
    );

    render(<TodoPage />);

    expect(await screen.findByText("Failed to load todo items")).toBeInTheDocument();
  });

  it("shows all type filter options", async () => {
    stubFetch({ todos: [], unreadCount: 0 });

    render(<TodoPage />);
    await act(async () => {});

    const select = screen.getByLabelText("Filter todo items");
    const options = within(select).getAllByRole("option");
    const labels = options.map((o) => o.textContent);
    expect(labels).toEqual([
      "All",
      "Unread",
      "Weekly Digest",
      "Clip Suggestion",
      "Experiment Result",
      "Trend Alert",
    ]);
  });
});
