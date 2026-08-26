"use client";

import { useState } from "react";
import { Check, ClipboardCopy, Hash } from "lucide-react";

import { cn } from "@/lib/utils";

type XPreviewProps = {
  caption: string | null;
  hashtags: string[] | null;
  platformHooks: string[] | null;
};

const MAX_CHARS = 280;

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

function CharacterCount({ count }: { count: number }) {
  const ratio = count / MAX_CHARS;
  let color = "text-muted-foreground";
  if (ratio > 0.9) color = "text-red-500";
  else if (ratio > 0.7) color = "text-amber-500";

  return (
    <span className={cn("text-[10px] tabular-nums", color)}>
      {count}/{MAX_CHARS}
    </span>
  );
}

export default function XPreview({ caption, hashtags, platformHooks }: XPreviewProps) {
  const hasFeatures = caption || (hashtags && hashtags.length > 0);

  if (hasFeatures) {
    return (
      <div className="space-y-3">
        <div className="relative mx-auto aspect-[16/10] w-full overflow-hidden rounded-xl border-2 border-x/40 bg-black">
          <div className="absolute left-2 top-2 rounded-md bg-black px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-white">
            X
          </div>

          <div className="flex h-full flex-col justify-between p-4 pt-10">
            {caption && (
              <div className="group relative">
                <p className="whitespace-pre-wrap break-words text-sm text-white">{caption}</p>
                <CopyButton text={caption} className="right-auto left-full ml-1 top-0" />
              </div>
            )}

            {hashtags && hashtags.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {hashtags.map((tag) => (
                  <span
                    key={tag}
                    className="group relative inline-flex items-center gap-1 rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-[#1d9bf0]"
                  >
                    <Hash className="h-2.5 w-2.5" />
                    {tag.replace(/^#/, "")}
                    <CopyButton text={`#${tag.replace(/^#/, "")}`} className="right-auto left-full ml-1 top-1/2 -translate-y-1/2" />
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2">
          <span className="text-[10px] text-muted-foreground">Character count</span>
          <CharacterCount count={caption?.length ?? 0} />
        </div>
      </div>
    );
  }

  const hooks = platformHooks ?? [];

  if (hooks.length > 0) {
    return (
      <div className="space-y-3 rounded-xl border-2 border-x/40 bg-x/5 p-4">
        <div className="flex items-center gap-2 text-x">
          <span className="text-xs font-bold uppercase tracking-wider">X</span>
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
    <div className="flex aspect-[16/10] items-center justify-center rounded-xl border-2 border-dashed border-x/30 bg-x/5">
      <p className="text-center text-sm text-muted-foreground">
        Generate adaptation to preview
      </p>
    </div>
  );
}
