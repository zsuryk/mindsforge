"use client";

import { useCallback, useEffect, useState } from "react";
import { Brain, Lightbulb, PencilLine, RefreshCw } from "lucide-react";

import { JsonTree } from "@/components/json-tree";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AgentMemory, fetchAgentMemory, updateAgentMemory } from "@/lib/api";
import { collectInsights } from "@/lib/insights";
import { cn } from "@/lib/utils";

function parseValueInput(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

export default function MemoryInspectorPage() {
  const [agentMemory, setAgentMemory] = useState<AgentMemory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [updating, setUpdating] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      setAgentMemory(await fetchAgentMemory());
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

  const insights = agentMemory ? collectInsights(agentMemory.memory) : [];

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
          </div>

          <section className="space-y-4">
            <h2 className="text-sm font-semibold text-foreground">Raw context</h2>
            <JsonTree data={agentMemory.memory} />
          </section>
        </div>
      )}
    </div>
  );
}