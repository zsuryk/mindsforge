import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatPage from "./chat/page";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

function emptyHistoryFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(jsonResponse({ messages: [] }))),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("ChatPage", () => {
  it("renders user, mind and system messages from the history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          messages: [
            {
              role: "system",
              text: "Experiment concluded on clip 'The big reveal'.",
              fingerprint: null,
            },
            { role: "user", text: "Make hooks bolder", fingerprint: "u1" },
            {
              role: "mind",
              text: "Got it — bolder hooks from now on.",
              fingerprint: "m1",
            },
          ],
        }),
      ),
    );

    render(<ChatPage />);

    expect(
      await screen.findByText("Experiment concluded on clip 'The big reveal'."),
    ).toBeInTheDocument();
    expect(screen.getByText("Make hooks bolder")).toBeInTheDocument();
    expect(screen.getByText("Got it — bolder hooks from now on.")).toBeInTheDocument();
  });

  it("optimistically renders the message, then renders the reply", async () => {
    const user = userEvent.setup();
    const send = deferred();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("/chat/messages")) return send.promise;
        return Promise.resolve(jsonResponse({ messages: [] }));
      }),
    );

    render(<ChatPage />);
    await screen.findByText(/conversation with your Mind starts here/i);

    await user.type(screen.getByLabelText(/message your mind/i), "Remember: bold hooks");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    expect(await screen.findByText("Remember: bold hooks")).toBeInTheDocument();

    send.resolve(jsonResponse({ reply: "Noted!", rules: [] }));

    expect(await screen.findByText("Noted!")).toBeInTheDocument();
  });

  it("shows 'your Mind is thinking…' while awaiting and hides it after", async () => {
    const user = userEvent.setup();
    const send = deferred();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("/chat/messages")) return send.promise;
        return Promise.resolve(jsonResponse({ messages: [] }));
      }),
    );

    render(<ChatPage />);
    await screen.findByText(/conversation with your Mind starts here/i);

    await user.type(screen.getByLabelText(/message your mind/i), "What's trending?");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    expect(await screen.findByText(/your mind is thinking/i)).toBeInTheDocument();

    send.resolve(jsonResponse({ reply: "I'll check.", rules: [] }));

    expect(await screen.findByText("I'll check.")).toBeInTheDocument();
    expect(screen.queryByText(/your mind is thinking/i)).not.toBeInTheDocument();
  });

  it("renders rule chips from the rules response", async () => {
    const user = userEvent.setup();
    const send = deferred();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("/chat/messages")) return send.promise;
        return Promise.resolve(jsonResponse({ messages: [] }));
      }),
    );

    render(<ChatPage />);
    await screen.findByText(/conversation with your Mind starts here/i);

    await user.type(screen.getByLabelText(/message your mind/i), "Always open with a bold hook");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    send.resolve(
      jsonResponse({
        reply: "Remembered.",
        rules: ["Always open with a bold hook"],
      }),
    );

    expect(
      await screen.findByText("Your Mind saved: Always open with a bold hook"),
    ).toBeInTheDocument();
  });

  it("renders trend chips from researchTrends", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("/chat/trends")) {
          return Promise.resolve(
            jsonResponse({
              results: [
                {
                  title: "Hook formulas that dominate 2026",
                  url: "https://example.com/hooks",
                  content: "Trending hook structures across shorts.",
                },
              ],
            }),
          );
        }
        return Promise.resolve(jsonResponse({ messages: [] }));
      }),
    );

    render(<ChatPage />);
    await screen.findByText(/conversation with your Mind starts here/i);

    await user.type(screen.getByLabelText(/research a trend/i), "hook formulas");
    await user.click(screen.getByRole("button", { name: /research trends/i }));

    expect(await screen.findByText(/researched trends for/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Hook formulas that dominate 2026" }),
    ).toHaveAttribute("href", "https://example.com/hooks");
  });

  it("renders an error banner with the backend message on 502", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(jsonResponse({ detail: "minds api down" }, 502)),
    );

    render(<ChatPage />);

    expect(await screen.findByText("minds api down")).toBeInTheDocument();
  });

  it("polls history while a reply is pending", async () => {
    vi.useFakeTimers();
    const userMessage = { role: "user", text: "First draft?", fingerprint: null };
    const historyBodies = [{ messages: [] }, { messages: [userMessage] }];
    const historyCalls: string[] = [];
    const send = deferred();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/chat/messages")) return send.promise;
        historyCalls.push(url);
        return Promise.resolve(
          jsonResponse(historyBodies.shift() ?? { messages: [] }),
        );
      }),
    );

    render(<ChatPage />);
    await act(async () => {});
    expect(
      screen.getByText(/conversation with your Mind starts here/i),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/message your mind/i), {
      target: { value: "First draft?" },
    });
    await act(async () => {});
    fireEvent.click(screen.getByRole("button", { name: /^send$/i }));
    await act(async () => {});

    expect(screen.getByText(/your mind is thinking/i)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });

    expect(
      historyCalls.filter((url) => url.includes("/chat/history")).length,
    ).toBeGreaterThan(1);
    expect(screen.getByText("First draft?")).toBeInTheDocument();
    expect(screen.getByText(/your mind is thinking/i)).toBeInTheDocument();

    send.resolve(jsonResponse({ reply: "Draft approved.", rules: [] }));
    await act(async () => {});

    expect(screen.getByText("Draft approved.")).toBeInTheDocument();
    expect(screen.queryByText(/your mind is thinking/i)).not.toBeInTheDocument();
  });

  it("surfaces a failing poll as a banner without losing the thread", async () => {
    vi.useFakeTimers();
    const historyBodies = [
      [{ role: "user", text: "Keep bolder hooks", fingerprint: "u1" }],
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("/chat/history")) {
          if (historyBodies.length > 0) {
            return Promise.resolve(
              jsonResponse({ messages: historyBodies.shift() }),
            );
          }
          return Promise.resolve(jsonResponse({ detail: "minds api down" }, 502));
        }
        return Promise.resolve(jsonResponse({ messages: [] }));
      }),
    );

    render(<ChatPage />);
    await act(async () => {});
    expect(screen.getByText("Keep bolder hooks")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });

    expect(screen.getByText("minds api down")).toBeInTheDocument();
    expect(screen.getByText("Keep bolder hooks")).toBeInTheDocument();
  });

  it("shows the empty state welcome copy when there is no history", async () => {
    emptyHistoryFetch();

    render(<ChatPage />);

    expect(
      await screen.findByText(/conversation with your Mind starts here/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/tell your Mind a brand rule, or ask it to research a trend/i),
    ).toBeInTheDocument();
  });
});