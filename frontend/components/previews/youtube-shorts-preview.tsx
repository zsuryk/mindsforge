"use client";

import { useState } from "react";
import { Check, ClipboardCopy, Play } from "lucide-react";

import { AdaptationAssets, AdaptationThumbnailVariant } from "@/lib/api";
import { mediaUrl } from "@/lib/api";
import { cn } from "@/lib/utils";

type YouTubeShortsPreviewProps = {
  thumbnailBriefs: Array<{ frame_timestamp: number; overlay_text: string }> | null;
  platformHooks: string[] | null;
  assets: AdaptationAssets | null;
};

function CopyHookButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="absolute right-2 top-2 rounded-md border border-white/20 bg-black/50 p-1.5 text-white opacity-0 transition-opacity hover:bg-black/70 group-hover:opacity-100"
      aria-label={`Copy hook: ${text}`}
    >
      {copied ? <Check className="h-3 w-3" /> : <ClipboardCopy className="h-3 w-3" />}
    </button>
  );
}

function ThumbnailCard({
  variant,
  large,
}: {
  variant: AdaptationThumbnailVariant;
  large?: boolean;
}) {
  return (
    <figure
      className={cn(
        "group relative overflow-hidden rounded-lg border border-youtube/30 bg-youtube/5",
        large ? "col-span-2 row-span-2" : "col-span-1",
      )}
    >
      <img
        src={mediaUrl(variant.url)}
        alt={`Thumbnail: ${variant.overlay_text || "variant"}`}
        className={cn("w-full object-cover", large ? "aspect-[9/16]" : "aspect-video")}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
      <figcaption className="absolute bottom-0 left-0 right-0 p-3">
        <p className="text-sm font-medium text-white drop-shadow-md">{variant.overlay_text}</p>
      </figcaption>
      <CopyHookButton text={variant.overlay_text} />
      <div className="absolute left-2 top-2 rounded-md bg-youtube px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-white">
        YouTube Shorts
      </div>
    </figure>
  );
}

function HookFallback({ hooks }: { hooks: string[] }) {
  return (
    <div className="space-y-3 rounded-xl border-2 border-youtube/40 bg-youtube/5 p-4">
      <div className="flex items-center gap-2 text-youtube">
        <Play className="h-4 w-4 fill-current" />
        <span className="text-xs font-bold uppercase tracking-wider">YouTube Shorts</span>
      </div>
      <ol className="space-y-2">
        {hooks.map((hook, index) => (
          <li
            key={hook}
            className="group relative flex items-start gap-2 rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-foreground"
          >
            <span className="shrink-0 text-xs text-muted-foreground">{index + 1}.</span>
            <span>{hook}</span>
            <CopyHookButton text={hook} />
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function YouTubeShortsPreview({
  thumbnailBriefs,
  platformHooks,
  assets,
}: YouTubeShortsPreviewProps) {
  const hasThumbnails = assets && assets.thumbnail_variants.length > 0;
  const hooks = platformHooks ?? [];

  if (hasThumbnails) {
    const variants = assets.thumbnail_variants;
    const large = variants[0];
    const small = variants.slice(1, 3);

    return (
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2">
          <ThumbnailCard variant={large} large />
          {small.map((variant) => (
            <ThumbnailCard key={variant.id} variant={variant} />
          ))}
        </div>
      </div>
    );
  }

  if (hooks.length > 0) {
    return <HookFallback hooks={hooks} />;
  }

  return (
    <div className="flex aspect-[9/16] items-center justify-center rounded-xl border-2 border-dashed border-youtube/30 bg-youtube/5">
      <p className="text-center text-sm text-muted-foreground">
        No Shorts preview available yet.
      </p>
    </div>
  );
}
