"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Brain,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  Pause,
  PencilLine,
  Play,
  RefreshCw,
  TrendingUp,
} from "lucide-react";

import { JsonTree } from "@/components/json-tree";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SystemMessageToggle } from "@/components/system-message-toggle";
import {
  AgentMemory,
  ChatMessage,
  TrendResult,
  WeeklyTrendsStatus,
  fetchAgentMemory,
  fetchChatHistory,
  fetchWeeklyTrendsStatus,
  toggleWeeklyTrends,
  triggerWeeklyTrendsRun,
  updateAgentMemory,
} from "@/lib/api";
import { collectInsights } from "@/lib/insights";
import { cn } from "@/lib/utils";
import { useSystemMessageFilter } from "@/hooks/use-system-message-filter";

function parseValueInput(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

type TrendEntry = {
  query: string;
  platform: string | null;
  source: string;
  results: TrendResult[];
  researched_at: string;
};

const PLATFORM_LABELS: Record<string, string> = {
  youtube: "YouTube",
  tiktok: "TikTok",
  x: "X",
};

function TrendEntryRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: TrendEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  const date = entry.researched_at
    ? new Date(entry.researched_at).toLocaleDateString()
    : "—";
  const platformLabel = entry.platform
    ? PLATFORM_LABELS[entry.platform] ?? entry.platform
    : "All";
  const sourceBadge =
    entry.source === "weekly" ? (
      <Badge variant="secondary" className="text-xs">
        auto
      </Badge>
    ) : (
      <Badge variant="outline" className="text-xs">
        manual
      </Badge>
    );

  return (
    <div className="border-b border-border/40 last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-secondary/30"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        <span className="font-medium text-foreground">{date}</span>
        <Badge variant="outline" className="text-xs">
          {platformLabel}
        </Badge>
        {sourceBadge}
        <span className="ml-auto text-xs text-muted-foreground">
          {entry.results.length} results
        </span>
      </button>
      {expanded && (
        <div className="space-y-2 px-4 pb-4 pl-11">
          <p className="text-xs font-medium text-muted-foreground">
            &apos;{entry.query}&apos;
          </p>
          {entry.results.length === 0 ? (
            <p className="text-xs text-muted-foreground">No results.</p>
          ) : (
            <ul className="space-y-1.5">
              {entry.results.map((result, i) => (
                <li key={i} className="text-xs">
                  <span className="font-medium text-foreground">
                    {result.title}
                  </span>
                  <a
                    href={result.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 text-primary underline-offset-2 hover:underline"
                  >
                    link
                  </a>
                  {result.content && (
                    <p className="mt-0.5 line-clamp-2 text-muted-foreground">
                      {result.content.slice(0, 200)}
                      {result.content.length > 200 && "…"}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function ChatHistoryRow({ message }: { message: ChatMessage }) {
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
    </div>
  );
}

export default function MemoryInspectorPage() {
  const [agentMemory, setAgentMemory] = useState<AgentMemory | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [updating, setUpdating] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);
  const [weeklyStatus, setWeeklyStatus] = useState<WeeklyTrendsStatus | null>(
    null,
  );
  const [runningWeekly, setRunningWeekly] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [memory, history, status] = await Promise.all([
        fetchAgentMemory(),
        fetchChatHistory(),
        fetchWeeklyTrendsStatus(),
      ]);
      setAgentMemory(memory);
      setChatHistory(history.messages);
      setWeeklyStatus(status);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load memory");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleUpdate = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedKey = key.trim();
    if (!trimmedKey || updating) return;

    setUpdating(true);
    setUpdateMessage(null);
    try {
      const success = await updateAgentMemory(trimmedKey, parseValueInput(value));
      if (success) {
        setUpdateMessage(`Saved “${trimmedKey}” to memory.`);
        setKey("");
        setValue("");
        await load();
      } else {
        setUpdateMessage("The mind did not confirm the update.");
      }
    } catch (err) {
      setUpdateMessage(err instanceof Error ? err.message : "Update failed.");
    } finally {
      setUpdating(false);
    }
  };

  const handleRunWeekly = async () => {
    setRunningWeekly(true);
    try {
      await triggerWeeklyTrendsRun();
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to run weekly trends",
      );
    } finally {
      setRunningWeekly(false);
    }
  };

  const handleTogglePause = async () => {
    if (!weeklyStatus) return;
    try {
      const newStatus = await toggleWeeklyTrends(!weeklyStatus.paused);
      setWeeklyStatus(newStatus);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to toggle weekly trends",
      );
    }
  };

  const toggleRow = (index: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const insights = agentMemory ? collectInsights(agentMemory.memory) : [];
  const trendHistory: TrendEntry[] =
    agentMemory &&
    Array.isArray(agentMemory.memory.trend_research)
      ? (agentMemory.memory.trend_research as TrendEntry[])
          .slice()
          .reverse()
      : [];
  const { showSystem, toggle, systemCount, filtered } = useSystemMessageFilter(chatHistory);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-border/40 bg-secondary/50">
            <Brain className="h-5 w-5 text-mind" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
              Memory Inspector
            </h1>
            {agentMemory && (
              <p className="mt-0.5 text-sm text-muted-foreground">
                Mind{" "}
                <Badge variant="outline" className="ml-1 font-mono text-xs">
                  {agentMemory.agent_id}
                </Badge>
              </p>
            )}
          </div>
        </div>
        <Button variant="outline" onClick={load} disabled={refreshing}>
          <RefreshCw className={cn(refreshing && "animate-spin")} />
          {refreshing ? "Refreshing…" : "Refresh"}
        </Button>
      </header>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {agentMemory === null ? (
        !error && <p className="text-sm text-muted-foreground">Loading memory…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-4">
            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-foreground">Learned rules</h2>
              {insights.length === 0 ? (
                <Card>
                  <CardContent className="p-6">
                    <p className="text-sm text-muted-foreground">
                      No learned rules yet — run A/B tests and write insights to see cards here.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {insights.map((insight, index) => (
                    <Card key={`${insight.title}-${index}`}>
                      <CardContent className="p-4">
                        <div className="mb-2 flex items-center gap-2">
                          <Lightbulb className="h-4 w-4 text-insight" />
                          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {insight.title}
                          </p>
                        </div>
                        <p className="line-clamp-3 text-sm text-foreground">{insight.detail}</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </section>

            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-foreground">
                  Weekly Trends
                </h2>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRunWeekly}
                    disabled={runningWeekly}
                  >
                    <TrendingUp
                      className={cn(runningWeekly && "animate-pulse")}
                    />
                    {runningWeekly ? "Running…" : "Run now"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleTogglePause}
                    disabled={!weeklyStatus}
                  >
                    {weeklyStatus?.paused ? (
                      <>
                        <Play className="h-3 w-3" /> Resume
                      </>
                    ) : (
                      <>
                        <Pause className="h-3 w-3" /> Pause
                      </>
                    )}
                  </Button>
                </div>
              </div>

              {weeklyStatus && (
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>
                    Last run:{" "}
                    {weeklyStatus.last_run
                      ? new Date(weeklyStatus.last_run).toLocaleString()
                      : "never"}
                  </span>
                  <span>
                    Next run:{" "}
                    {weeklyStatus.paused
                      ? "paused"
                      : weeklyStatus.next_run
                        ? new Date(weeklyStatus.next_run).toLocaleString()
                        : "—"}
                  </span>
                </div>
              )}

              <Card>
                <CardContent className="p-0">
                  {trendHistory.length === 0 ? (
                    <div className="p-6">
                      <p className="text-sm text-muted-foreground">
                        No trend research yet — run weekly trends or search from
                        chat to see results here.
                      </p>
                    </div>
                  ) : (
                    <div>
                      {trendHistory.map((entry, index) => (
                        <TrendEntryRow
                          key={index}
                          entry={entry}
                          expanded={expandedRows.has(index)}
                          onToggle={() => toggleRow(index)}
                        />
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </section>

            <Card>
              <CardHeader className="pb-4">
                <CardTitle className="text-sm font-semibold">Write to memory</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleUpdate} className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="memory-key">Key</Label>
                      <Input
                        id="memory-key"
                        type="text"
                        value={key}
                        onChange={(event) => setKey(event.target.value)}
                        placeholder="e.g. tiktok_best_pacing"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="memory-value">Value</Label>
                      <Input
                        id="memory-value"
                        type="text"
                        value={value}
                        onChange={(event) => setValue(event.target.value)}
                        placeholder='JSON or text, e.g. {"ctr": 0.03}'
                      />
                    </div>
                  </div>
                  <Button type="submit" disabled={updating || !key.trim()}>
                    <PencilLine />
                    {updating ? "Writing…" : "Write to memory"}
                  </Button>
                  {updateMessage && <p className="text-sm text-muted-foreground">{updateMessage}</p>}
                </form>
              </CardContent>
            </Card>

            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-foreground">Raw context</h2>
              <JsonTree data={agentMemory.memory} />
            </section>
          </div>

          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">Mind's View</h2>
              <SystemMessageToggle
                showSystem={showSystem}
                onToggle={toggle}
                count={systemCount}
              />
            </div>
            <Card>
              <CardContent className="p-4">
                {chatHistory.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No conversation history yet — start chatting with your Mind to see its native memory here.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {filtered.map((message, index) => (
                      <ChatHistoryRow key={index} message={message} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </section>
        </div>
      )}
    </div>
  );
}