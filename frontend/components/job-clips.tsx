"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Clip, fetchJobClips, mediaUrl } from "@/lib/api";

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export default function JobClips({ jobId }: { jobId: string }) {
  const [clips, setClips] = useState<Clip[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJobClips(jobId)
      .then((result) => {
        if (!cancelled) setClips(result);
      })
      .catch(() => {
        if (!cancelled) setClips([]);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (clips === null) {
    return <p className="px-6 pb-4 text-xs text-muted-foreground">Loading clips…</p>;
  }

  if (clips.length === 0) {
    return <p className="px-6 pb-4 text-xs text-muted-foreground">No clips extracted.</p>;
  }

  return (
    <div className="grid gap-4 px-6 py-5 sm:grid-cols-2 lg:grid-cols-3">
      {clips.map((clip) => (
        <article
          key={clip.id}
          className="overflow-hidden rounded-lg border border-border/40 bg-background/60"
        >
          <video
            controls
            preload="metadata"
            poster={clip.thumbnail_url ? mediaUrl(clip.thumbnail_url) : undefined}
            src={mediaUrl(clip.video_url)}
            className="aspect-video w-full bg-black"
          />
          <div className="space-y-1 p-4">
            <p className="truncate text-sm font-medium text-foreground" title={clip.title}>
              {clip.title}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatTime(clip.start_time)} – {formatTime(clip.end_time)}
            </p>
            <p className="line-clamp-2 text-xs text-muted-foreground">{clip.transcript_text}</p>
            <Button variant="secondary" size="sm" asChild className="mt-2">
              <a href={`/clips/${clip.id}`}>
                <FlaskConical />
                Open in studio
                <ArrowUpRight />
              </a>
            </Button>
          </div>
        </article>
      ))}
    </div>
  );
}
