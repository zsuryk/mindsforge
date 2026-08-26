"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, FlaskConical } from "lucide-react";
import Link from "next/link";

import LaunchAbTestModal from "@/components/launch-ab-test-modal";
import AdaptationStudio from "@/components/adaptation-studio";
import PlatformPreviewCanvas from "@/components/previews/platform-preview-canvas";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Clip, fetchClip, mediaUrl } from "@/lib/api";

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

function ScrollableTranscript({ text }: { text: string }) {
  const [scrollable, setScrollable] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => setScrollable(el.scrollHeight > el.clientHeight + 1);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, [text]);

  return (
    <div className="relative">
      <div ref={ref} className="max-h-[min(45vh,24rem)] overflow-y-auto">
        <p className="text-sm leading-relaxed text-foreground">{text}</p>
      </div>
      {scrollable && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-background to-transparent"
        />
      )}
    </div>
  );
}

export default function ClipStudioPage() {
  const { id } = useParams<{ id: string }>();
  const [clip, setClip] = useState<Clip | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  return (
    <div className="mx-auto max-w-7xl space-y-8">
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
              <ScrollableTranscript text={clip.transcript_text} />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4 lg:sticky lg:top-4 lg:self-start lg:row-span-2">
          <PlatformPreviewCanvas clip={clip} />
        </div>

        <div className="space-y-4 lg:col-span-2">
          <AdaptationStudio clipId={clip.id} />
        </div>
      </div>

      <LaunchAbTestModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        clipId={clip.id}
        suggestedTitles={metadata?.suggested_titles ?? []}
      />
    </div>
  );
}