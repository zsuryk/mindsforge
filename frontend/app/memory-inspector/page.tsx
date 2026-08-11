"use client";

import { useCallback, useEffect, useState } from "react";
import { Brain, Lightbulb, PencilLine, RefreshCw } from "lucide-react";

import { JsonTree } from "@/components/json-tree";
import { AgentMemory, fetchAgentMemory, updateAgentMemory } from "@/lib/api";
import { collectInsights } from "@/lib/insights";

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
    <div className="space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-800 bg-slate-900">
            <Brain className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">Memory Inspector</h1>
            {agentMemory && (
              <p className="text-xs text-slate-500">
                Agent{" "}
                <span className="rounded-md border border-slate-800 bg-slate-900 px-1.5 py-0.5 font-mono text-slate-300">
                  {agentMemory.agent_id}
                </span>
              </p>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition-colors hover:border-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </p>
      )}

      {agentMemory === null ? (
        !error && <p className="text-sm text-slate-500">Loading memory…</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-6">
            <section className="space-y-3">
              <h2 className="text-sm font-medium text-slate-400">Learned rules</h2>
              {insights.length === 0 ? (
                <p className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-sm text-slate-500">
                  No learned rules yet — run A/B tests and write insights to see cards here.
                </p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {insights.map((insight, index) => (
                    <div
                      key={`${insight.title}-${index}`}
                      className="rounded-xl border border-slate-800 bg-slate-900 p-4"
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <Lightbulb className="h-4 w-4 text-amber-300" />
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                          {insight.title}
                        </p>
                      </div>
                      <p className="line-clamp-3 text-sm text-slate-200">{insight.detail}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <h2 className="mb-3 text-sm font-medium text-slate-400">Write to memory</h2>
              <form onSubmit={handleUpdate} className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <label htmlFor="memory-key" className="text-sm font-medium text-slate-300">
                      Key
                    </label>
                    <input
                      id="memory-key"
                      type="text"
                      value={key}
                      onChange={(event) => setKey(event.target.value)}
                      placeholder="e.g. tiktok_best_pacing"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="memory-value" className="text-sm font-medium text-slate-300">
                      Value
                    </label>
                    <input
                      id="memory-value"
                      type="text"
                      value={value}
                      onChange={(event) => setValue(event.target.value)}
                      placeholder='JSON or text, e.g. {"ctr": 0.03}'
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={updating || !key.trim()}
                  className="flex items-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <PencilLine className="h-4 w-4" />
                  {updating ? "Writing…" : "Write to memory"}
                </button>
                {updateMessage && <p className="text-sm text-slate-400">{updateMessage}</p>}
              </form>
            </section>
          </div>

          <section className="space-y-3">
            <h2 className="text-sm font-medium text-slate-400">Raw context</h2>
            <JsonTree data={agentMemory.memory} />
          </section>
        </div>
      )}
    </div>
  );
}
