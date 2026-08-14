"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, ClipboardCopy, Download, FlaskConical, Wand2 } from "lucide-react";

import LaunchAbTestModal from "@/components/launch-ab-test-modal";
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

const POLL_INTERVAL_MS = 1500;

const STATUS_STYLE: Record<string, string> = {
  PENDING: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  GENERATING: "border-indigo-500/40 bg-indigo-500/10 text-indigo-300",
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
        <span
          key={tag}
          className="rounded-full border border-slate-700 bg-slate-800 px-2.5 py-0.5 text-xs text-slate-200"
        >
          {tag}
        </span>
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
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {label}
        </p>
        <button
          type="button"
          onClick={handleCopy}
          aria-label={`Copy ${label}`}
          className="flex items-center gap-1 rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:border-indigo-500 hover:text-indigo-300"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <ClipboardCopy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {children ? (
        children
      ) : (
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-slate-200">
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
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        STATUS_STYLE[status] ?? "border-slate-700 bg-slate-900 text-slate-300"
      }`}
    >
      {status === "GENERATING" && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {status}
    </span>
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
          <p className="text-sm text-slate-500">No thumbnails rendered for this surface.</p>
        ) : (
          variants.map((variant) => (
            <figure key={variant.id} className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
              <img
                src={mediaUrl(variant.url)}
                alt={`Thumbnail: ${variant.overlay_text || "variant"}`}
                className="aspect-video w-full object-cover"
              />
              <figcaption className="truncate px-2 py-1.5 text-xs text-slate-400">
                {variant.overlay_text || variant.id}
              </figcaption>
            </figure>
          ))
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {assets.captions_url && (
          <a
            href={mediaUrl(assets.captions_url)}
            download
            className="flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 hover:border-indigo-500 hover:text-indigo-300"
          >
            <Download className="h-3.5 w-3.5" />
            captions.srt
          </a>
        )}
        {assets.chapters_url && (
          <a
            href={mediaUrl(assets.chapters_url)}
            download
            className="flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 hover:border-indigo-500 hover:text-indigo-300"
          >
            <Download className="h-3.5 w-3.5" />
            chapters.txt
          </a>
        )}
        {platform === "youtube" && variants.length >= 2 && (
          <button
            type="button"
            onClick={() => onTest(variants)}
            className="ml-auto flex items-center gap-1.5 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-400"
          >
            <FlaskConical className="h-3.5 w-3.5" />
            Run Test &amp; Compare
          </button>
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
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Adaptation studio
        </h2>
        <button
          type="button"
          onClick={load}
          className="text-xs text-slate-500 hover:text-slate-200"
        >
          Refresh
        </button>
      </div>

      <div className="mb-4 flex flex-wrap gap-1 rounded-lg border border-slate-800 bg-slate-950 p-1">
        {ADAPTATION_TARGETS.map((target) => (
          <button
            key={targetKey(target)}
            onClick={() => setActiveTarget(target)}
            aria-selected={activeTarget === target}
            className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
              activeTarget === target
                ? "bg-indigo-500 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {target.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </p>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {adaptation === null ? (
            <p className="text-sm text-slate-500">
              No adaptation generated for {activeTarget.label} yet.
            </p>
          ) : (
            <>
              <StatusBadge status={adaptation.status} />
              {adaptation.error_message && (
                <p className="text-xs text-red-400">{adaptation.error_message}</p>
              )}
            </>
          )}
        </div>
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isBusy}
          className="flex items-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Wand2 className="h-4 w-4" />
          {isBusy
            ? "Generating…"
            : adaptation?.status === "FAILED"
              ? "Retry"
              : "Generate"}
        </button>
      </div>

      {adaptation?.status === "READY" && (
        <div className="space-y-5">
          {adaptation.features && (
            <div className="grid gap-3 lg:grid-cols-2">
              {manifestPanels(adaptation.features).map((panel) => (
                <CopyBlock
                  key={panel.key}
                  label={panel.label}
                  lines={panel.lines}
                >
                  {panel.key === "tags" && <TagChips tags={panel.lines} />}
                </CopyBlock>
              ))}
            </div>
          )}

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Assets
            </p>
            {adaptation.assets ? (
              <AssetGrid
                assets={adaptation.assets}
                platform={adaptation.platform}
                onTest={handleTest}
              />
            ) : (
              <p className="text-sm text-slate-500">No assets rendered yet.</p>
            )}
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Publish checklist
            </p>
            <ol className="space-y-1.5">
              {(PUBLISH_STEPS[targetKey(activeTarget)] ?? []).map((step, index) => {
                const id = `${targetKey(activeTarget)}:${index}`;
                return (
                  <li key={id}>
                    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 p-2.5 text-sm text-slate-200 hover:border-slate-700">
                      <input
                        type="checkbox"
                        checked={checked[id] ?? false}
                        onChange={() =>
                          setChecked((current) => ({ ...current, [id]: !current[id] }))
                        }
                        className="accent-indigo-500"
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
    </div>
  );
}
