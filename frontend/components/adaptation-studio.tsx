"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, ClipboardCopy, Download, FlaskConical, Wand2 } from "lucide-react";

import LaunchAbTestModal from "@/components/launch-ab-test-modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Adaptation,
  AdaptationAssets,
  AdaptationThumbnailVariant,
  fetchAdaptation,
  fetchAdaptations,
  generateAdaptation,
  mediaUrl,
} from "@/lib/api";
import { ADAPTATION_TARGETS, AdaptationTarget } from "@/lib/platforms";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 1500;

const STATUS_STYLE: Record<string, string> = {
  PENDING: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  GENERATING: "border-border bg-secondary/70 text-muted-foreground",
  READY: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  FAILED: "border-red-500/30 bg-red-500/10 text-red-300",
};

const PUBLISH_STEPS: Record<string, string[]> = {
  "youtube/SHORTS": [
    "Upload the short",
    "Open with the hook",
    "Paste the caption",
    "Run Test & Compare on the thumbnails",
  ],
  "youtube/LONG_FORM": [
    "Upload the video",
    "Paste chapters into the description",
    "Add the tags",
    "Attach the poll and quiz",
    "Run Test & Compare on the thumbnails",
  ],
  "tiktok/POST": [
    "Upload the video",
    "Paste the caption",
    "Add sticker suggestions",
    "Pin the comment",
  ],
  "x/POST": [
    "Compose the post with the caption",
    "Add the hashtags",
    "Pin the post",
  ],
};

function targetKey(target: AdaptationTarget): string {
  return `${target.platform}/${target.surface}`;
}

function formatClock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

function recordLines(record: Record<string, unknown>): string[] {
  const parts: string[] = [];
  for (const field of [
    "title",
    "text",
    "question",
    "answer",
    "emoji",
    "placement",
    "style",
    "timestamp",
  ]) {
    if (record[field] !== undefined && record[field] !== null) {
      parts.push(
        field === "timestamp" ? formatClock(Number(record[field])) : String(record[field]),
      );
    }
  }
  if (parts.length === 0) {
    const keys = Object.keys(record);
    if (keys.length > 0) parts.push(String(record[keys[0]]));
  }
  return parts;
}

function featureLines(features: Record<string, unknown>, key: string): string[] | null {
  const value = features[key];
  if (value === null || value === undefined) return null;
  if (Array.isArray(value)) {
    return value.map((item) => {
      if (typeof item === "string") return item;
      return recordLines(item as Record<string, unknown>).join(" — ");
    });
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const lines: string[] = [];
    if (record.question) lines.push(`Question: ${record.question}`);
    if (Array.isArray(record.options)) {
      lines.push(...record.options.map((option) => `- ${String(option)}`));
    }
    if (lines.length === 0) lines.push(recordLines(record).join(" — "));
    return lines;
  }
  return [String(value)];
}

function TagChips({ tags }: { tags: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag) => (
        <Badge key={tag} variant="outline">
          {tag}
        </Badge>
      ))}
    </div>
  );
}

function CopyBlock({
  label,
  lines,
  children,
}: {
  label: string;
  lines: string[];
  children?: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable (e.g. non-secure context) — panel stays copyable by hand
    }
  };

  return (
    <div className="rounded-lg border border-border/40 bg-background/60 p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          aria-label={`Copy ${label}`}
        >
          {copied ? (
            <Check className="text-emerald-400" />
          ) : (
            <ClipboardCopy />
          )}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      {children ? (
        children
      ) : (
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground">
          {lines.join("\n")}
        </pre>
      )}
    </div>
  );
}

function manifestPanels(features: Record<string, unknown>) {
  const panels: { label: string; key: string }[] = [
    { label: "Chapters", key: "chapters" },
    { label: "Tags", key: "tags" },
    { label: "Poll", key: "poll" },
    { label: "Quiz", key: "quiz" },
    { label: "Stickers", key: "stickers" },
    { label: "Pinned comment", key: "pinned_comment" },
    { label: "Overlay styles", key: "overlay_spec" },
    { label: "Caption style", key: "caption_style" },
    { label: "Shorts link", key: "shorts_link" },
    { label: "Caption", key: "caption" },
    { label: "Hashtags", key: "hashtags" },
    { label: "Platform hooks", key: "platform_hooks" },
  ];
  return panels
    .map((panel) => ({ ...panel, lines: featureLines(features, panel.key) }))
    .filter((panel) => panel.lines !== null) as { label: string; key: string; lines: string[] }[];
}

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge
      variant="outline"
      className={cn(STATUS_STYLE[status] ?? "border-border bg-secondary/70 text-muted-foreground")}
    >
      {status === "GENERATING" && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {status}
    </Badge>
  );
}

function AssetGrid({
  assets,
  platform,
  onTest,
}: {
  assets: AdaptationAssets;
  platform: string;
  onTest: (variants: AdaptationThumbnailVariant[]) => void;
}) {
  const variants = assets.thumbnail_variants ?? [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {variants.length === 0 ? (
          <p className="text-sm text-muted-foreground">No thumbnails rendered for this surface.</p>
        ) : (
          variants.map((variant) => (
            <figure
              key={variant.id}
              className="overflow-hidden rounded-lg border border-border/40 bg-background/60"
            >
              <img
                src={mediaUrl(variant.url)}
                alt={`Thumbnail: ${variant.overlay_text || "variant"}`}
                className="aspect-video w-full object-cover"
              />
              <figcaption className="truncate px-2 py-1.5 text-xs text-muted-foreground">
                {variant.overlay_text || variant.id}
              </figcaption>
            </figure>
          ))
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {assets.captions_url && (
          <Button variant="outline" size="sm" asChild>
            <a href={mediaUrl(assets.captions_url)} download>
              <Download />
              captions.srt
            </a>
          </Button>
        )}
        {assets.chapters_url && (
          <Button variant="outline" size="sm" asChild>
            <a href={mediaUrl(assets.chapters_url)} download>
              <Download />
              chapters.txt
            </a>
          </Button>
        )}
        {platform === "youtube" && variants.length >= 2 && (
          <Button size="sm" className="ml-auto" onClick={() => onTest(variants)}>
            <FlaskConical />
            Run Test &amp; Compare
          </Button>
        )}
      </div>
    </div>
  );
}

export default function AdaptationStudio({ clipId }: { clipId: string }) {
  const [adaptations, setAdaptations] = useState<Adaptation[] | null>(null);
  const [activeTarget, setActiveTarget] = useState<AdaptationTarget>(ADAPTATION_TARGETS[0]);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [testOpen, setTestOpen] = useState(false);
  const [testVariants, setTestVariants] = useState<AdaptationThumbnailVariant[]>([]);

  const upsert = useCallback((fresh: Adaptation) => {
    setAdaptations((current) => {
      if (current === null) return [fresh];
      const index = current.findIndex((item) => item.id === fresh.id);
      if (index === -1) return [...current, fresh];
      const next = [...current];
      next[index] = fresh;
      return next;
    });
  }, []);

  const load = useCallback(async () => {
    try {
      setAdaptations(await fetchAdaptations(clipId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load adaptations");
    }
  }, [clipId]);

  useEffect(() => {
    load();
  }, [load]);

  const adaptation =
    adaptations?.find(
      (item) =>
        item.platform === activeTarget.platform &&
        item.surface === activeTarget.surface,
    ) ?? null;

  const handleGenerate = async () => {
    setError(null);
    try {
      const created = await generateAdaptation(
        clipId,
        activeTarget.platform,
        activeTarget.surface,
      );
      upsert(created);
      const poll = async (adaptationId: string) => {
        try {
          const fresh = await fetchAdaptation(clipId, adaptationId);
          upsert(fresh);
          if (fresh.status === "PENDING" || fresh.status === "GENERATING") {
            window.setTimeout(() => poll(adaptationId), POLL_INTERVAL_MS);
          }
        } catch {
          // a failed refresh leaves the last known state visible
        }
      };
      poll(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate adaptation");
    }
  };

  const handleTest = (variants: AdaptationThumbnailVariant[]) => {
    setTestVariants(variants);
    setTestOpen(true);
  };

  const isBusy = adaptation?.status === "PENDING" || adaptation?.status === "GENERATING";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Adaptation studio
        </CardTitle>
        <Button type="button" variant="ghost" size="sm" onClick={load}>
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <Tabs
          value={targetKey(activeTarget)}
          onValueChange={(next) => {
            const target = ADAPTATION_TARGETS.find((item) => targetKey(item) === next);
            if (target) setActiveTarget(target);
          }}
        >
          <TabsList className="grid w-full grid-cols-4">
            {ADAPTATION_TARGETS.map((target) => (
              <TabsTrigger key={targetKey(target)} value={targetKey(target)} className="px-2 text-xs">
                {target.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {ADAPTATION_TARGETS.map((target) => (
            <TabsContent key={targetKey(target)} value={targetKey(target)}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  {adaptation === null ? (
                    <p className="text-sm text-muted-foreground">
                      No adaptation generated for {target.label.toLowerCase()} yet.
                    </p>
                  ) : (
                    <>
                      <StatusBadge status={adaptation.status} />
                      {adaptation.error_message && (
                        <p className="text-xs text-destructive">{adaptation.error_message}</p>
                      )}
                    </>
                  )}
                </div>
                <Button type="button" onClick={handleGenerate} disabled={isBusy}>
                  <Wand2 />
                  {isBusy
                    ? "Generating…"
                    : adaptation?.status === "FAILED"
                      ? "Retry"
                      : "Generate"}
                </Button>
              </div>
            </TabsContent>
          ))}
        </Tabs>

        {error && (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
        )}

        {adaptation?.status === "READY" && (
          <div className="space-y-5">
            {adaptation.features && (
              <div className="grid gap-3 lg:grid-cols-2">
                {manifestPanels(adaptation.features).map((panel) => (
                  <CopyBlock key={panel.key} label={panel.label} lines={panel.lines}>
                    {panel.key === "tags" && <TagChips tags={panel.lines} />}
                  </CopyBlock>
                ))}
              </div>
            )}

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Assets
              </p>
              {adaptation.assets ? (
                <AssetGrid
                  assets={adaptation.assets}
                  platform={adaptation.platform}
                  onTest={handleTest}
                />
              ) : (
                <p className="text-sm text-muted-foreground">No assets rendered yet.</p>
              )}
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Publish checklist
              </p>
              <ol className="space-y-1.5">
                {(PUBLISH_STEPS[targetKey(activeTarget)] ?? []).map((step, index) => {
                  const id = `${targetKey(activeTarget)}:${index}`;
                  return (
                    <li key={id}>
                      <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-border/40 bg-background/60 p-2.5 text-sm text-foreground transition-colors hover:border-border">
                        <input
                          type="checkbox"
                          checked={checked[id] ?? false}
                          onChange={() =>
                            setChecked((current) => ({ ...current, [id]: !current[id] }))
                          }
                          className="size-4 accent-primary"
                        />
                        {step}
                      </label>
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>
        )}

        <LaunchAbTestModal
          open={testOpen}
          onClose={() => setTestOpen(false)}
          clipId={clipId}
          suggestedTitles={[]}
          variantKind="THUMBNAIL"
          thumbnailVariants={testVariants}
          platform={
            activeTarget.platform === "youtube"
              ? activeTarget.surface === "LONG_FORM"
                ? "youtube"
                : "youtube_shorts"
              : activeTarget.platform
          }
        />
      </CardContent>
    </Card>
  );
}