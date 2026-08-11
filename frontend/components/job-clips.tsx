"use client";

import { useEffect, useState } from "react";

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
    return <p className="px-5 pb-4 text-xs text-slate-500">Loading clips…</p>;
  }

  if (clips.length === 0) {
    return <p className="px-5 pb-4 text-xs text-slate-500">No clips extracted.</p>;
  }

  return (
    <div className="grid gap-4 px-5 pb-5 sm:grid-cols-2 lg:grid-cols-3">
      {clips.map((clip) => (
        <article
          key={clip.id}
          className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950"
        >
          <video
            controls
            preload="metadata"
            poster={clip.thumbnail_url ? mediaUrl(clip.thumbnail_url) : undefined}
            src={mediaUrl(clip.video_url)}
            className="aspect-video w-full bg-black"
          />
          <div className="space-y-1 p-3">
            <p className="truncate text-sm font-medium text-slate-100" title={clip.title}>
              {clip.title}
            </p>
            <p className="text-xs text-slate-500">
              {formatTime(clip.start_time)} – {formatTime(clip.end_time)}
            </p>
            <p className="line-clamp-2 text-xs text-slate-400">{clip.transcript_text}</p>
          </div>
        </article>
      ))}
    </div>
  );
}
