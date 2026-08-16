"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, FlaskConical, Quote } from "lucide-react";

import LaunchAbTestModal from "@/components/launch-ab-test-modal";
import AdaptationStudio from "@/components/adaptation-studio";
import ViralityGauge, { viralityColor, viralityLabel } from "@/components/virality-gauge";
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
        <p className="rounded-lg border border-edge bg-card p-4 text-sm text-muted">
          {error}
        </p>
      </div>
    );
  }

  if (clip === null) {
    return <p className="text-sm text-subtle">Loading clip…</p>;
  }

  const metadata = clip.suggested_hooks;
  const platformHooks = metadata?.platform_hooks ?? null;
  const hooks = platformHooks?.[activeTab] ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <a
            href="/jobs"
            className="mb-2 inline-flex items-center gap-1 text-xs text-muted transition-colors hover:text-fg"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to jobs
          </a>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-fg">
            {clip.title}
          </h1>
          <p className="text-xs text-subtle">
            {formatTime(clip.start_time)} – {formatTime(clip.end_time)} ·{" "}
            {clip.transcript_text.split(/\s+/).filter(Boolean).length} words
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground transition-colors hover:bg-accent-hover"
        >
          <FlaskConical className="h-4 w-4" />
          Launch A/B Test
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="overflow-hidden rounded-xl border border-edge bg-card">
            <video
              controls
              preload="metadata"
              poster={clip.thumbnail_url ? mediaUrl(clip.thumbnail_url) : undefined}
              src={mediaUrl(clip.video_url)}
              className="aspect-video w-full bg-black"
            />
          </div>
          <div className="rounded-xl border border-edge bg-card p-5">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted">
              Transcript
            </h2>
            <p className="text-sm leading-relaxed text-fg">{clip.transcript_text}</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-edge bg-card p-5">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted">
              Virality score
            </h2>
            <ViralityGauge score={clip.virality_score} />
            {clip.virality_score !== null && (
              <p
                className="mt-2 text-center text-xs"
                style={{ color: viralityColor(clip.virality_score) }}
              >
                {viralityLabel(clip.virality_score)}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-edge bg-card p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
              Platform hooks
            </h2>
            {platformHooks === null ? (
              <p className="text-sm text-subtle">No hooks yet — scoring pending.</p>
            ) : (
              <>
                <div className="mb-3 flex gap-1 rounded-lg border border-edge bg-background p-1">
                  {PLATFORMS.map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      aria-selected={activeTab === tab.key}
                      className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                        activeTab === tab.key
                          ? "bg-accent text-accent-foreground"
                          : "text-muted hover:text-fg"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                {hooks.length === 0 ? (
                  <p className="text-sm text-subtle">No hooks for this platform.</p>
                ) : (
                  <ol className="space-y-2">
                    {hooks.map((hook, index) => (
                      <li
                        key={hook}
                        className="flex items-start gap-2 rounded-lg border border-edge bg-background p-3 text-sm text-fg"
                      >
                        <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                        <span>
                          <span className="mr-1 text-xs text-subtle">{index + 1}.</span>
                          {hook}
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </>
            )}
          </div>
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
