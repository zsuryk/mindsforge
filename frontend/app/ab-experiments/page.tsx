"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3, FlaskConical, RefreshCw, Trophy } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AbExperiment, AbVariant, fetchAbExperiments, mediaUrl } from "@/lib/api";
import { PLATFORMS } from "@/lib/platforms";

const POLL_INTERVAL_MS = 10_000;

function platformLabel(platform: string): string {
  return PLATFORMS.find((option) => option.key === platform)?.label ?? platform;
}

function formatViews(views: number): string {
  return views.toLocaleString("en-US");
}

function chartName(title: string): string {
  return title.length > 18 ? `${title.slice(0, 17)}…` : title;
}

export default function AbExperimentsPage() {
  const [experiments, setExperiments] = useState<AbExperiment[] | null>(null);
  const [viewThreshold, setViewThreshold] = useState(1000);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const payload = await fetchAbExperiments();
      setExperiments(payload.experiments);
      setViewThreshold(payload.view_threshold);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load experiments");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const poll = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(poll);
  }, [load]);

  const active = (experiments ?? []).filter((exp) => exp.status === "ACTIVE");
  const concluded = (experiments ?? []).filter((exp) => exp.status === "CONCLUDED");

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-800 bg-slate-900">
            <BarChart3 className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">A/B Experiments</h1>
            <p className="text-xs text-slate-500">
              Variants run until {formatViews(viewThreshold)}+ cumulative views, then the
              winner is written to memory.
            </p>
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

      {experiments === null ? (
        !error && <p className="text-sm text-slate-500">Loading experiments…</p>
      ) : (
        <>
          <section className="space-y-4">
            <h2 className="text-sm font-medium text-slate-400">
              Active tests{" "}
              <span className="text-slate-600">({active.length})</span>
            </h2>
            {active.length === 0 ? (
              <p className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-sm text-slate-500">
                No active tests — launch an A/B test from the clip studio.
              </p>
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {active.map((experiment) => (
                  <ActiveExperimentCard
                    key={experiment.id}
                    experiment={experiment}
                    viewThreshold={viewThreshold}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-4">
            <h2 className="text-sm font-medium text-slate-400">
              Concluded{" "}
              <span className="text-slate-600">({concluded.length})</span>
            </h2>
            {concluded.length === 0 ? (
              <p className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-sm text-slate-500">
                No concluded tests yet — concluded insights land here and in the
                Memory Inspector.
              </p>
            ) : (
              <div className="space-y-6">
                {concluded.map((experiment) => (
                  <ConcludedExperimentCard key={experiment.id} experiment={experiment} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function CtrChart({ variants, barColor }: { variants: AbVariant[]; barColor: string }) {
  const chartData = variants.map((variant) => ({
    name: chartName(variant.title),
    ctr: variant.ctr,
    fullTitle: variant.title,
  }));

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} stroke="#334155" />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} stroke="#334155" unit="%" />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f172a",
              border: "1px solid #334155",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(value: number) => [`${value.toFixed(2)}%`, "CTR"]}
            labelFormatter={(_: string, payload) =>
              payload && payload[0] ? payload[0].payload.fullTitle : ""
            }
          />
          <Bar dataKey="ctr" fill={barColor} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ActiveExperimentCard({
  experiment,
  viewThreshold,
}: {
  experiment: AbExperiment;
  viewThreshold: number;
}) {
  const totalViews = experiment.variants.reduce((sum, variant) => sum + variant.views, 0);
  const progress = Math.min(100, Math.round((totalViews / viewThreshold) * 100));
  const winner = experiment.variants.reduce<AbVariant | null>(
    (best, variant) => (best === null || variant.ctr > best.ctr ? variant : best),
    null,
  );

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-100">{experiment.clip_title}</p>
          <p className="text-xs text-slate-500">
            {platformLabel(experiment.platform)} · {experiment.variants.length} variants
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className="flex items-center gap-1.5 rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2.5 py-1 text-xs font-medium text-indigo-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-400" />
            ACTIVE
          </span>
          {experiment.variant_kind === "THUMBNAIL" && (
            <span className="rounded-full border border-slate-600 bg-slate-800/60 px-2.5 py-1 text-xs font-medium text-slate-300">
              thumbnail variants
            </span>
          )}
        </div>
      </div>

      <div className="space-y-2.5">
        {experiment.variants.map((variant) => (
          <div
            key={variant.variant_id}
            className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950 p-3"
          >
            {variant.thumbnail_url ? (
              <img
                src={mediaUrl(variant.thumbnail_url)}
                alt=""
                className="h-10 w-16 shrink-0 rounded-md object-cover"
              />
            ) : (
              <div className="flex h-10 w-16 shrink-0 items-center justify-center rounded-md bg-slate-800 text-xs text-slate-600">
                no thumb
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-slate-200">{variant.title}</p>
              <p className="text-xs text-slate-500">
                {formatViews(variant.views)} views · {variant.ctr.toFixed(2)}% CTR
              </p>
            </div>
            {winner && variant.variant_id === winner.variant_id && variant.ctr > 0 && (
              <span className="shrink-0 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-300">
                leading
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-4">
        <div>
          <div className="mb-1 flex justify-between text-xs text-slate-500">
            <span>Cumulative views</span>
            <span>
              {formatViews(totalViews)} / {formatViews(viewThreshold)}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            CTR comparison
          </p>
          <CtrChart variants={experiment.variants} barColor="#818cf8" />
        </div>
      </div>
    </div>
  );
}

function ConcludedExperimentCard({ experiment }: { experiment: AbExperiment }) {
  const winner = experiment.variants.find(
    (variant) => variant.variant_id === experiment.winning_variant_id,
  );

  return (
    <div className="overflow-hidden rounded-xl border border-emerald-500/30 bg-slate-900">
      <div className="flex items-start gap-3 border-b border-emerald-500/20 bg-emerald-500/10 p-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/20">
          <Trophy className="h-5 w-5 text-emerald-300" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
            Winner · {platformLabel(experiment.platform)} ·{" "}
            {experiment.clip_title}
          </p>
          <p className="mt-1 text-lg font-semibold text-slate-100">
            {winner?.title ?? "No winner recorded"}
          </p>
          {winner && (
            <p className="text-xs text-slate-400">
              {formatViews(winner.views)} views · {winner.ctr.toFixed(2)}% CTR
            </p>
          )}
        </div>
      </div>

      <div className="space-y-4 p-5">
        {experiment.learned_insight && (
          <div className="rounded-lg border border-slate-800 bg-slate-950 p-4 text-sm leading-relaxed text-slate-200">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-amber-300">
              Learned insight — written to memory
            </span>
            {experiment.learned_insight}
          </div>
        )}

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            CTR comparison
          </p>
          <CtrChart variants={experiment.variants} barColor="#10b981" />
        </div>

        <p className="flex items-center gap-1.5 text-xs text-slate-500">
          <FlaskConical className="h-3 w-3" />
          Concluded after{" "}
          {formatViews(
            experiment.variants.reduce((sum, variant) => sum + variant.views, 0),
          )}{" "}
          total views
        </p>
      </div>
    </div>
  );
}
