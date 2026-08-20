"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3, FlaskConical, Pencil, RefreshCw, Trophy } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  AbExperiment,
  AbExperimentVariantKind,
  AbVariant,
  fetchAbExperiments,
  mediaUrl,
  updateAbVariantMetrics,
} from "@/lib/api";
import { EXPERIMENT_PLATFORMS } from "@/lib/platforms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 10_000;

function platformLabel(platform: string): string {
  return EXPERIMENT_PLATFORMS.find((option) => option.key === platform)?.label ?? platform;
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
  const failed = (experiments ?? []).filter((exp) => exp.status === "FAILED");

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-border/40 bg-secondary/50">
            <BarChart3 className="h-5 w-5 text-muted-foreground" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
              A/B Experiments
            </h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Variants run until {formatViews(viewThreshold)}+ cumulative views, then the
              winner is written to memory.
            </p>
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

      {experiments === null ? (
        !error && <p className="text-sm text-muted-foreground">Loading experiments…</p>
      ) : (
        <>
          <section className="space-y-4">
            <h2 className="text-sm font-semibold text-foreground">
              Active tests{" "}
              <span className="font-normal text-muted-foreground">({active.length})</span>
            </h2>
            {active.length === 0 ? (
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm text-muted-foreground">
                    No active tests — launch an A/B test from the clip studio.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {active.map((experiment) => (
                  <ActiveExperimentCard
                    key={experiment.id}
                    experiment={experiment}
                    viewThreshold={viewThreshold}
                    onUpdated={load}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-4">
            <h2 className="text-sm font-semibold text-foreground">
              Concluded{" "}
              <span className="font-normal text-muted-foreground">({concluded.length})</span>
            </h2>
            {concluded.length === 0 ? (
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm text-muted-foreground">
                    No concluded tests yet — concluded insights land here and in the
                    Memory Inspector.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {concluded.map((experiment) => (
                  <ConcludedExperimentCard key={experiment.id} experiment={experiment} />
                ))}
              </div>
            )}
          </section>

          {failed.length > 0 && (
            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-foreground">
                Failed{" "}
                <span className="font-normal text-muted-foreground">({failed.length})</span>
              </h2>
              <div className="space-y-4">
                {failed.map((experiment) => (
                  <FailedExperimentCard key={experiment.id} experiment={experiment} />
                ))}
              </div>
            </section>
          )}
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
          <CartesianGrid stroke="hsl(var(--edge) / 0.5)" strokeDasharray="3 3" />
          <XAxis
            dataKey="name"
            tick={{ fill: "hsl(var(--muted))", fontSize: 11 }}
            stroke="hsl(var(--edge))"
          />
          <YAxis
            tick={{ fill: "hsl(var(--muted))", fontSize: 11 }}
            stroke="hsl(var(--edge))"
            unit="%"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--edge))",
              borderRadius: 8,
              fontSize: 12,
              color: "hsl(var(--fg))",
            }}
            labelStyle={{ color: "hsl(var(--fg))" }}
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
  onUpdated,
}: {
  experiment: AbExperiment;
  viewThreshold: number;
  onUpdated: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState({ views: "", clicks: "" });
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const totalViews = experiment.variants.reduce((sum, variant) => sum + variant.views, 0);
  const progress = Math.min(100, Math.round((totalViews / viewThreshold) * 100));
  const winner = experiment.variants.reduce<AbVariant | null>(
    (best, variant) => (best === null || variant.ctr > best.ctr ? variant : best),
    null,
  );

  const startEdit = (variant: AbVariant) => {
    setEditingId(variant.variant_id);
    setDraft({ views: String(variant.views), clicks: String(variant.clicks) });
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditError(null);
  };

  const saveMetrics = async (variantId: string) => {
    const views = Number(draft.views);
    const clicks = Number(draft.clicks);
    if (
      !Number.isInteger(views) ||
      views < 0 ||
      !Number.isInteger(clicks) ||
      clicks < 0
    ) {
      setEditError("Views and clicks must be whole, non-negative numbers.");
      return;
    }
    if (clicks > views) {
      setEditError("Clicks cannot exceed views.");
      return;
    }
    setSaving(true);
    try {
      await updateAbVariantMetrics(experiment.id, variantId, views, clicks);
      setEditingId(null);
      setEditError(null);
      onUpdated();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to save metrics");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="h-fit">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-sm font-semibold">{experiment.clip_title}</CardTitle>
            <CardDescription className="mt-1">
              {platformLabel(experiment.platform)} · {experiment.variants.length} variants
            </CardDescription>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <Badge className="border-primary/40 bg-primary/10 text-primary">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
              ACTIVE
            </Badge>
            {experiment.data_source === "MANUAL" ? (
              <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-300">
                manual
              </Badge>
            ) : (
              <Badge variant="outline">simulated</Badge>
            )}
            {experiment.variant_kind === AbExperimentVariantKind.THUMBNAIL && (
              <Badge variant="outline">thumbnail variants</Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2.5">
          {experiment.variants.map((variant) => (
            <VariantRow
              key={variant.variant_id}
              variant={variant}
              leading={
                winner !== null &&
                variant.variant_id === winner.variant_id &&
                variant.ctr > 0
              }
              onEdit={startEdit}
              editing={editingId === variant.variant_id}
              draftViews={editingId === variant.variant_id ? draft.views : ""}
              draftClicks={editingId === variant.variant_id ? draft.clicks : ""}
              onDraftViews={(value) => setDraft((current) => ({ ...current, views: value }))}
              onDraftClicks={(value) => setDraft((current) => ({ ...current, clicks: value }))}
              onSave={saveMetrics}
              onCancel={cancelEdit}
              saving={saving}
              editError={editingId === variant.variant_id ? editError : null}
            />
          ))}
        </div>

        <div className="space-y-4">
          <div>
            <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
              <span>Cumulative views</span>
              <span>
                {formatViews(totalViews)} / {formatViews(viewThreshold)}
              </span>
            </div>
            <Progress value={progress} />
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              CTR comparison
            </p>
            <CtrChart variants={experiment.variants} barColor="hsl(var(--fg))" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function VariantRow({
  variant,
  leading = false,
  onEdit,
  editing = false,
  draftViews = "",
  draftClicks = "",
  onDraftViews,
  onDraftClicks,
  onSave,
  onCancel,
  saving = false,
  editError = null,
}: {
  variant: AbVariant;
  leading?: boolean;
  onEdit?: (variant: AbVariant) => void;
  editing?: boolean;
  draftViews?: string;
  draftClicks?: string;
  onDraftViews?: (value: string) => void;
  onDraftClicks?: (value: string) => void;
  onSave?: (variantId: string) => void;
  onCancel?: () => void;
  saving?: boolean;
  editError?: string | null;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/40 bg-background/60 p-3">
      {variant.thumbnail_url ? (
        <img
          src={mediaUrl(variant.thumbnail_url)}
          alt=""
          className="h-10 w-16 shrink-0 rounded-md border border-border/40 object-cover"
        />
      ) : (
        <div className="flex h-10 w-16 shrink-0 items-center justify-center rounded-md bg-secondary/70 text-xs text-muted-foreground">
          no thumb
        </div>
      )}
      {editing ? (
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="truncate text-sm text-foreground">{variant.title}</p>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="number"
              min={0}
              value={draftViews}
              onChange={(event) => onDraftViews?.(event.target.value)}
              aria-label={`views for ${variant.title}`}
              className="h-8 w-24"
            />
            <Input
              type="number"
              min={0}
              value={draftClicks}
              onChange={(event) => onDraftClicks?.(event.target.value)}
              aria-label={`clicks for ${variant.title}`}
              className="h-8 w-24"
            />
            <Button size="sm" onClick={() => onSave?.(variant.variant_id)} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          </div>
          {editError && <p className="text-xs text-destructive">{editError}</p>}
        </div>
      ) : (
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm text-foreground">{variant.title}</p>
          <p className="text-xs text-muted-foreground">
            {formatViews(variant.views)} views · {variant.clicks} clicks · {variant.ctr.toFixed(2)}% CTR
          </p>
        </div>
      )}
      {!editing && leading && (
        <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
          leading
        </Badge>
      )}
      {!editing && onEdit && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onEdit(variant)}
          aria-label={`Edit metrics for ${variant.title}`}
        >
          <Pencil className="h-3.5 w-3.5" />
          Edit
        </Button>
      )}
    </div>
  );
}

function FailedExperimentCard({ experiment }: { experiment: AbExperiment }) {
  return (
    <Card className="overflow-hidden border-destructive/30">
      <CardHeader className="border-b border-destructive/20 bg-destructive/10">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-destructive/20">
            <FlaskConical className="h-5 w-5 text-destructive" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-destructive">
              Failed · {platformLabel(experiment.platform)} · {experiment.clip_title}
            </p>
            <p className="mt-1 text-sm text-foreground">
              {experiment.variant_kind === AbExperimentVariantKind.THUMBNAIL
                ? "Thumbnail variants"
                : "Title variants"}{" "}
              · {experiment.variants.length} variants
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-5">
        {experiment.error_message ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            {experiment.error_message}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No error message recorded.</p>
        )}
        <div className="space-y-2">
          {experiment.variants.map((variant) => (
            <VariantRow key={variant.variant_id} variant={variant} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ConcludedExperimentCard({ experiment }: { experiment: AbExperiment }) {
  const winner = experiment.variants.find(
    (variant) => variant.variant_id === experiment.winning_variant_id,
  );

  return (
    <Card className="overflow-hidden border-emerald-500/30">
      <CardHeader className="border-b border-emerald-500/20 bg-emerald-500/10">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/20">
            <Trophy className="h-5 w-5 text-emerald-300" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
              Winner · {platformLabel(experiment.platform)} · {experiment.clip_title}
            </p>
            <p className="mt-1 text-lg font-semibold tracking-tight text-foreground">
              {winner?.title ?? "No winner recorded"}
            </p>
            {winner && (
              <p className="mt-0.5 text-xs text-muted-foreground">
                {formatViews(winner.views)} views · {winner.ctr.toFixed(2)}% CTR
              </p>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-5">
        {experiment.learned_insight && (
          <div className="rounded-lg border border-border/40 bg-background/60 p-4 text-sm leading-relaxed text-foreground">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-insight">
              Learned insight — written to memory
            </span>
            {experiment.learned_insight}
          </div>
        )}

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            CTR comparison
          </p>
          <CtrChart variants={experiment.variants} barColor="#34d399" />
        </div>

        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <FlaskConical className="h-3 w-3" />
          Concluded after{" "}
          {formatViews(
            experiment.variants.reduce((sum, variant) => sum + variant.views, 0),
          )}{" "}
          total views
        </p>
      </CardContent>
    </Card>
  );
}
