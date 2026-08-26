"use client";

import { useState } from "react";

import ViralityGauge, { viralityColor, viralityLabel } from "@/components/virality-gauge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AdaptationSummary, Clip } from "@/lib/api";
import { ADAPTATION_TARGETS, AdaptationTarget } from "@/lib/platforms";

import TikTokPreview from "./tiktok-preview";
import XPreview from "./x-preview";
import YouTubeLongFormPreview from "./youtube-longform-preview";
import YouTubeShortsPreview from "./youtube-shorts-preview";

type PlatformPreviewCanvasProps = {
  clip: Clip;
};

function targetKey(target: AdaptationTarget): string {
  return `${target.platform}/${target.surface}`;
}

function platformHooksKey(target: AdaptationTarget): string {
  if (target.platform === "youtube" && target.surface === "SHORTS") {
    return "youtube_shorts";
  }
  return target.platform;
}

function findAdaptation(
  adaptations: AdaptationSummary[],
  target: AdaptationTarget,
): AdaptationSummary | null {
  return (
    adaptations.find(
      (a) => a.platform === target.platform && a.surface === target.surface,
    ) ?? null
  );
}

function YouTubeVideoFallback() {
  return (
    <div className="flex aspect-video items-center justify-center rounded-xl border-2 border-dashed border-muted-foreground/20 bg-muted/20">
      <p className="text-center text-sm text-muted-foreground">
        Generate adaptation to preview
      </p>
    </div>
  );
}

function PreviewContent({
  target,
  adaptation,
  platformHooks,
}: {
  target: AdaptationTarget;
  adaptation: AdaptationSummary | null;
  platformHooks: Record<string, string[]> | null;
}) {
  const hooks = platformHooks?.[platformHooksKey(target)] ?? [];

  if (target.surface === "SHORTS") {
    return (
      <YouTubeShortsPreview
        thumbnailBriefs={
          adaptation?.features?.thumbnail_briefs as Array<{
            frame_timestamp: number;
            overlay_text: string;
          }> | null
        }
        platformHooks={hooks}
        assets={adaptation?.assets ?? null}
      />
    );
  }

  if (target.surface === "LONG_FORM") {
    if (!adaptation?.features) {
      return <YouTubeVideoFallback />;
    }

    const features = adaptation.features as {
      chapters?: Array<{ title: string; timestamp: number }>;
      poll?: { question: string; options: string[] };
      quiz?: Array<{ question: string; answer: string }>;
      thumbnail_briefs?: Array<{ frame_timestamp: number; overlay_text: string }>;
      shorts_link?: string;
    };

    return (
      <YouTubeLongFormPreview
        chapters={features.chapters ?? null}
        poll={features.poll ?? null}
        quiz={features.quiz ?? null}
        thumbnailBriefs={features.thumbnail_briefs ?? null}
        shortsLink={features.shorts_link ?? null}
      />
    );
  }

  if (target.platform === "tiktok") {
    const features = adaptation?.features as {
      overlay_spec?: Array<{ text: string; placement: string; style: string }>;
      caption_style?: string;
      stickers?: Array<{ emoji: string; placement: string }>;
      pinned_comment?: string;
    } | null;

    return (
      <TikTokPreview
        overlaySpec={features?.overlay_spec ?? null}
        captionStyle={features?.caption_style ?? null}
        stickers={features?.stickers ?? null}
        pinnedComment={features?.pinned_comment ?? null}
        platformHooks={hooks}
      />
    );
  }

  if (target.platform === "x") {
    const features = adaptation?.features as {
      caption?: string;
      hashtags?: string[];
    } | null;

    return (
      <XPreview
        caption={features?.caption ?? null}
        hashtags={features?.hashtags ?? null}
        platformHooks={hooks}
      />
    );
  }

  return null;
}

export default function PlatformPreviewCanvas({ clip }: PlatformPreviewCanvasProps) {
  const [activeTarget, setActiveTarget] = useState<AdaptationTarget>(ADAPTATION_TARGETS[0]);
  const adaptations = clip.latest_adaptations ?? [];
  const adaptation = findAdaptation(adaptations, activeTarget);
  const platformHooks = clip.suggested_hooks?.platform_hooks ?? null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Virality score
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <ViralityGauge score={clip.virality_score} />
        {clip.virality_score !== null && (
          <p
            className="text-center text-xs"
            style={{ color: viralityColor(clip.virality_score) }}
          >
            {viralityLabel(clip.virality_score)}
          </p>
        )}

        <Tabs
          value={targetKey(activeTarget)}
          onValueChange={(next) => {
            const target = ADAPTATION_TARGETS.find((t) => targetKey(t) === next);
            if (target) setActiveTarget(target);
          }}
        >
          <TabsList className="grid w-full grid-cols-4">
            {ADAPTATION_TARGETS.map((target) => (
              <TabsTrigger
                key={targetKey(target)}
                value={targetKey(target)}
                className="px-2 text-xs"
              >
                {target.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {ADAPTATION_TARGETS.map((target) => (
            <TabsContent key={targetKey(target)} value={targetKey(target)}>
              <PreviewContent
                target={target}
                adaptation={findAdaptation(adaptations, target)}
                platformHooks={platformHooks}
              />
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}
