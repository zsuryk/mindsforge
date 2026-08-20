"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Brain, MessageCircle, Search, Send } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  ChatMessage,
  fetchChatHistory,
  researchTrends,
  sendChatMessage,
  TrendResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 5_000;

function isInHistory(history: ChatMessage[], message: ChatMessage): boolean {
  return history.some(
    (row) => row.role === message.role && row.text === message.text,
  );
}

function MessageBubble({
  message,
  rules,
}: {
  message: ChatMessage;
  rules?: string[];
}) {
  if (message.role === "system") {
    return (
      <div className="flex justify-center">
        <p className="max-w-[80%] rounded-full border border-border/40 bg-secondary/50 px-3 py-1.5 text-center text-xs leading-relaxed text-muted-foreground">
          {message.text}
        </p>
      </div>
    );
  }

  if (message.role === "mind") {
    return (
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-mind/15 text-mind ring-1 ring-mind/30">
          <Brain className="h-4 w-4" />
        </div>
        <div className="max-w-[75%] whitespace-pre-wrap rounded-2xl rounded-tl-sm border border-border/40 bg-card px-4 py-3 text-sm leading-relaxed text-foreground">
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="max-w-[75%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-primary px-4 py-3 text-sm leading-relaxed text-primary-foreground">
        {message.text}
      </div>
      {rules?.map((rule) => (
        <p
          key={rule}
          className="rounded-full border border-insight/30 bg-insight/10 px-3 py-1 text-xs text-insight"
        >
          Your Mind saved: {rule}
        </p>
      ))}
    </div>
  );
}

function ThinkingRow() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-mind/15 text-mind ring-1 ring-mind/30">
        <Brain className="h-4 w-4" />
      </div>
      <p className="rounded-2xl rounded-tl-sm border border-border/40 bg-card px-4 py-3 text-sm text-muted-foreground">
        Your Mind is thinking
        <span className="inline-flex w-6 justify-between">
          <span className="animate-pulse">.</span>
          <span className="animate-pulse [animation-delay:150ms]">.</span>
          <span className="animate-pulse [animation-delay:300ms]">.</span>
        </span>
      </p>
    </div>
  );
}

function TrendChip({
  query,
  results,
}: {
  query: string;
  results: TrendResult[];
}) {
  return (
    <div className="flex justify-center">
      <div className="max-w-[85%] rounded-2xl border border-border/40 bg-secondary/40 px-4 py-2.5 text-xs text-muted-foreground">
        <p className="mb-1.5 font-medium text-foreground">
          Researched trends for “{query}”
        </p>
        <ul className="space-y-1">
          {results.slice(0, 5).map((result) => (
            <li key={result.url}>
              <a
                href={result.url}
                target="_blank"
                rel="noreferrer"
                className="text-mind underline decoration-mind/40 underline-offset-2 hover:text-mind-fg"
              >
                {result.title}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function ChatPage() {
  const [history, setHistory] = useState<ChatMessage[] | null>(null);
  const [pending, setPending] = useState<ChatMessage[]>([]);
  const [savedRules, setSavedRules] = useState<Record<string, string[]>>({});
  const [thinking, setThinking] = useState(false);
  const [draft, setDraft] = useState("");
  const [trendQuery, setTrendQuery] = useState("");
  const [trendResult, setTrendResult] = useState<{
    query: string;
    results: TrendResult[];
  } | null>(null);
  const [researching, setResearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async () => {
    try {
      const payload = await fetchChatHistory();
      setHistory(payload.messages);
      setPending((current) =>
        current.filter((message) => !isInHistory(payload.messages, message)),
      );
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load chat history",
      );
    }
  }, []);

  useEffect(() => {
    loadHistory();
    const poll = setInterval(loadHistory, POLL_INTERVAL_MS);
    return () => clearInterval(poll);
  }, [loadHistory]);

  const messageCount = (history?.length ?? 0) + pending.length;
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messageCount, thinking, trendResult]);

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || thinking) return;
    const optimistic: ChatMessage = { role: "user", text, fingerprint: null };
    setPending((current) => [...current, optimistic]);
    setDraft("");
    setThinking(true);
    setError(null);
    try {
      const result = await sendChatMessage(text);
      if (result.rules.length > 0) {
        setSavedRules((current) => ({ ...current, [text]: result.rules }));
      }
      setPending((current) => [
        ...current,
        { role: "mind", text: result.reply, fingerprint: null },
      ]);
    } catch (err) {
      setPending((current) => current.filter((message) => message !== optimistic));
      setError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setThinking(false);
      loadHistory();
    }
  };

  const handleTrendResearch = async () => {
    const query = trendQuery.trim();
    if (!query || researching) return;
    setResearching(true);
    setError(null);
    try {
      const payload = await researchTrends(query);
      setTrendResult({ query, results: payload.results });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to research trends");
    } finally {
      setResearching(false);
    }
  };

  const thread: ChatMessage[] = [...(history ?? []), ...pending];
  const isEmpty = history !== null && thread.length === 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-border/40 bg-secondary/50">
          <MessageCircle className="h-5 w-5 text-muted-foreground" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
            Chat
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Talk to your Mind — it remembers what you tell it.
          </p>
        </div>
      </header>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="flex h-[calc(100vh-16rem)] min-h-[28rem] flex-col overflow-hidden">
        <div
          ref={scrollRef}
          className="flex-1 space-y-4 overflow-y-auto p-4"
          data-testid="thread"
        >
          {history === null ? (
            !error && (
              <p className="text-sm text-muted-foreground">Loading the thread…</p>
            )
          ) : isEmpty ? (
            <div className="flex h-full items-center justify-center">
              <div className="max-w-md text-center">
                <p className="font-display text-lg font-semibold tracking-tight text-foreground">
                  Your conversation with your Mind starts here
                </p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Tell your Mind a brand rule, or ask it to research a trend.
                </p>
              </div>
            </div>
          ) : (
            <>
              {thread.map((message, index) => (
                <div
                  key={`${message.role}:${message.text}:${index}`}
                  className={cn(
                    message.role === "user" ? "flex justify-end" : undefined,
                  )}
                >
                  <MessageBubble
                    message={message}
                    rules={
                      message.role === "user" ? savedRules[message.text] : undefined
                    }
                  />
                </div>
              ))}
              {thinking && <ThinkingRow />}
            </>
          )}
          {trendResult && (
            <TrendChip query={trendResult.query} results={trendResult.results} />
          )}
        </div>

        <div className="space-y-3 border-t border-border/40 bg-background/40 p-3">
          <form
            className="flex items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              handleSend();
            }}
          >
            <Input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Message your Mind…"
              aria-label="Message your Mind"
              className="flex-1"
            />
            <Button type="submit" disabled={thinking || !draft.trim()}>
              <Send />
              Send
            </Button>
          </form>
          <form
            className="flex items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              handleTrendResearch();
            }}
          >
            <Input
              value={trendQuery}
              onChange={(event) => setTrendQuery(event.target.value)}
              placeholder="Research a trend…"
              aria-label="Research a trend"
              className="flex-1"
            />
            <Button
              type="submit"
              variant="outline"
              disabled={researching || !trendQuery.trim()}
            >
              <Search />
              {researching ? "Researching…" : "Research trends"}
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
}