"use client";

import { useState } from "react";
import { Check, ClipboardCopy, Music } from "lucide-react";

import { cn } from "@/lib/utils";

type OverlaySpecItem = {
  text: string;
  placement: string;
  style: string;
};

type StickerSuggestion = {
  emoji: string;
  placement: string;
};

type TikTokPreviewProps = {
  overlaySpec: OverlaySpecItem[] | null;
  captionStyle: string | null;
  stickers: StickerSuggestion[] | null;
  pinnedComment: string | null;
  platformHooks: string[] | null;
};

function CopyButton({ text, className }: { text: string; className?: string }) {
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
      className={cn(
        "absolute right-2 top-2 rounded-md border border-white/20 bg-black/50 p-1.5 text-white opacity-0 transition-opacity hover:bg-black/70 group-hover:opacity-100",
        className,
      )}
      aria-label={`Copy: ${text}`}
    >
      {copied ? <Check className="h-3 w-3" /> : <ClipboardCopy className="h-3 w-3" />}
    </button>
  );
}

function overlayPlacementClass(placement: string): string {
  switch (placement) {
    case "top":
      return "top-4 left-0 right-0 text-center";
    case "bottom":
      return "bottom-16 left-0 right-0 text-center";
    case "center":
    default:
      return "top-1/2 left-0 right-0 -translate-y-1/2 text-center";
  }
}

function overlayStyleClass(style: string): string {
  const lower = (style ?? "").toLowerCase();
  if (lower.includes("outlined") || lower.includes("outline")) {
    return "font-bold text-white drop-shadow-[0_1px_0_black,0_0_4px_black] [-webkit-text-stroke:1px_black]";
  }
  if (lower.includes("italic")) {
    return "italic text-white drop-shadow-md";
  }
  return "font-bold text-white drop-shadow-md";
}

function stickerPositionClass(placement: string): string {
  const lower = (placement ?? "").toLowerCase();
  if (lower.includes("top-right")) return "top-12 right-3";
  if (lower.includes("top-left")) return "top-12 left-3";
  if (lower.includes("bottom-right")) return "bottom-20 right-3";
  if (lower.includes("bottom-left")) return "bottom-20 left-3";
  if (lower.includes("top")) return "top-12 left-1/2 -translate-x-1/2";
  if (lower.includes("bottom")) return "bottom-20 left-1/2 -translate-x-1/2";
  return "top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2";
}

export default function TikTokPreview({
  overlaySpec,
  captionStyle,
  stickers,
  pinnedComment,
  platformHooks,
}: TikTokPreviewProps) {
  const hasFeatures =
    (overlaySpec && overlaySpec.length > 0) ||
    (stickers && stickers.length > 0) ||
    pinnedComment ||
    captionStyle;

  const hooks = platformHooks ?? [];

  if (hasFeatures) {
    return (
      <div className="space-y-3">
        <div className="relative mx-auto aspect-[9/16] w-full max-w-[200px] overflow-hidden rounded-xl border-2 border-black/40 bg-black">
          <div className="absolute left-2 top-2 rounded-md bg-[#010101] px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-[#25F4EE]">
            TikTok
          </div>

          {overlaySpec?.map((overlay, i) => (
            <div
              key={i}
              className={cn(
                "absolute px-4 text-sm",
                overlayPlacementClass(overlay.placement),
                overlayStyleClass(overlay.style),
              )}
            >
              <span className="group relative inline-block">
                {overlay.text}
                <CopyButton text={overlay.text} className="right-auto left-full ml-1 top-0" />
              </span>
            </div>
          ))}

          {stickers?.map((sticker, i) => (
            <span
              key={i}
              className={cn("absolute text-2xl", stickerPositionClass(sticker.placement))}
              role="img"
              aria-label={`Sticker: ${sticker.emoji}`}
            >
              {sticker.emoji}
            </span>
          ))}
        </div>

        {captionStyle && (
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
            <Music className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Caption:</span>
            <span className="text-xs font-medium text-foreground">{captionStyle}</span>
          </div>
        )}

        {pinnedComment && (
          <div className="group relative rounded-xl bg-[#010101] p-3">
            <div className="flex items-start gap-2">
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#25F4EE]/20 text-[10px] font-bold text-[#25F4EE]">
                PP
              </div>
              <div className="flex-1">
                <p className="text-[10px] font-semibold text-muted-foreground">Pinned comment</p>
                <p className="mt-0.5 text-xs text-foreground">{pinnedComment}</p>
              </div>
            </div>
            <CopyButton text={pinnedComment} />
          </div>
        )}
      </div>
    );
  }

  if (hooks.length > 0) {
    return (
      <div className="space-y-3 rounded-xl border-2 border-tiktok/40 bg-tiktok/5 p-4">
        <div className="flex items-center gap-2 text-tiktok">
          <Music className="h-4 w-4" />
          <span className="text-xs font-bold uppercase tracking-wider">TikTok</span>
        </div>
        <ol className="space-y-2">
          {hooks.map((hook, index) => (
            <li
              key={hook}
              className="group relative flex items-start gap-2 rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-foreground"
            >
              <span className="shrink-0 text-xs text-muted-foreground">{index + 1}.</span>
              <span>{hook}</span>
              <CopyButton text={hook} />
            </li>
          ))}
        </ol>
      </div>
    );
  }

  return (
    <div className="flex aspect-[9/16] items-center justify-center rounded-xl border-2 border-dashed border-tiktok/30 bg-tiktok/5">
      <p className="text-center text-sm text-muted-foreground">
        No TikTok preview available yet.
      </p>
    </div>
  );
}
