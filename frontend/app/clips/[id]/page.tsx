"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, FlaskConical, Quote } from "lucide-react";
import Link from "next/link";

import LaunchAbTestModal from "@/components/launch-ab-test-modal";
import AdaptationStudio from "@/components/adaptation-studio";
import ViralityGauge, { viralityColor, viralityLabel } from "@/components/virality-gauge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Clip, fetchClip, mediaUrl } from "@/lib/api";
import { PLATFORMS } from "@/lib/platforms";

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export default function ClipStudioPage() {
  const { id } = useParams<{ id: string }>();
  const [clip, setClip] = useState<Clip | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<(typeof PLATFORMS)[number]["key"]>(
    "youtube_shorts",
  );
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchClip(id)
      .then((result) => {
        if (!cancelled) setClip(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load clip");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-4xl">
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </p>
      </div>
    );
  }

  if (clip === null) {
    return <p className="text-sm text-muted-foreground">Loading clip…</p>;
  }

  const metadata = clip.suggested_hooks;
  const platformHooks = metadata?.platform_hooks ?? null;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link
            href="/jobs"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to jobs
          </Link>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
            {clip.title}
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {formatTime(clip.start_time)} – {formatTime(clip.end_time)} ·{" "}
            {clip.transcript_text.split(/\s+/).filter(Boolean).length} words
          </p>
        </div>
        <Button onClick={() => setModalOpen(true)} size="lg">
          <FlaskConical />
          Launch A/B Test
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card className="overflow-hidden p-0">
            <video
              controls
              preload="metadata"
              poster={clip.thumbnail_url ? mediaUrl(clip.thumbnail_url) : undefined}
              src={mediaUrl(clip.video_url)}
              className="aspect-video w-full bg-black"
            />
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Transcript
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed text-foreground">{clip.transcript_text}</p>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Virality score
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ViralityGauge score={clip.virality_score} />
              {clip.virality_score !== null && (
                <p
                  className="mt-2 text-center text-xs"
                  style={{ color: viralityColor(clip.virality_score) }}
                >
                  {viralityLabel(clip.virality_score)}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Platform hooks
              </CardTitle>
            </CardHeader>
            <CardContent>
              {platformHooks === null ? (
                <p className="text-sm text-muted-foreground">No hooks yet — scoring pending.</p>
              ) : (
                <>
                  <Tabs
                    value={activeTab}
                    onValueChange={(next) =>
                      setActiveTab(next as (typeof PLATFORMS)[number]["key"])
                    }
                  >
                    <TabsList className="grid w-full grid-cols-3">
                      {PLATFORMS.map((tab) => (
                        <TabsTrigger key={tab.key} value={tab.key} className="px-2 text-xs">
                          {tab.label}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    {PLATFORMS.map((tab) => {
                      const tabHooks = platformHooks?.[tab.key] ?? [];
                      return (
                        <TabsContent key={tab.key} value={tab.key}>
                          {tabHooks.length === 0 ? (
                            <p className="text-sm text-muted-foreground">
                              No hooks for this platform.
                            </p>
                          ) : (
                            <ol className="space-y-2">
                              {tabHooks.map((hook, index) => (
                                <li
                                  key={hook}
                                  className="flex items-start gap-2 rounded-lg border border-border/40 bg-background/60 p-3 text-sm text-foreground"
                                >
                                  <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                  <span>
                                    <span className="mr-1 text-xs text-muted-foreground">
                                      {index + 1}.
                                    </span>
                                    {hook}
                                  </span>
                                </li>
                              ))}
                            </ol>
                          )}
                        </TabsContent>
                      );
                    })}
                  </Tabs>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <AdaptationStudio clipId={clip.id} />

      <LaunchAbTestModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        clipId={clip.id}
        suggestedTitles={metadata?.suggested_titles ?? []}
      />
    </div>
  );
}