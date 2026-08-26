"use client";

import { useState } from "react";
import { Check, ClipboardCopy, Clock, HelpCircle, List, Play } from "lucide-react";

import { cn } from "@/lib/utils";

type ChapterItem = { title: string; timestamp: number };
type CommunityPoll = { question: string; options: string[] };
type QuizItem = { question: string; answer: string };
type ThumbnailBrief = { frame_timestamp: number; overlay_text: string };

type YouTubeLongFormPreviewProps = {
  chapters: ChapterItem[] | null;
  poll: CommunityPoll | null;
  quiz: QuizItem[] | null;
  thumbnailBriefs: ThumbnailBrief[] | null;
  shortsLink: string | null;
};

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

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

function PollCard({ poll }: { poll: CommunityPoll }) {
  return (
    <div className="group relative space-y-3 rounded-lg border border-youtube/30 bg-youtube/5 p-4">
      <div className="flex items-center gap-2 text-youtube">
        <HelpCircle className="h-4 w-4" />
        <span className="text-xs font-bold uppercase tracking-wider">Poll</span>
      </div>
      <p className="text-sm font-medium text-foreground">{poll.question}</p>
      <ul className="space-y-2">
        {poll.options.map((option, i) => (
          <li
            key={option}
            className="flex items-center gap-2 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-foreground"
          >
            <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-muted-foreground/40">
              <span className="h-2 w-2 rounded-full bg-muted-foreground/30" />
            </span>
            {option}
          </li>
        ))}
      </ul>
      <CopyButton text={poll.question} />
    </div>
  );
}

function QuizCard({ quiz }: { quiz: QuizItem[] }) {
  return (
    <div className="space-y-3 rounded-lg border border-youtube/30 bg-youtube/5 p-4">
      <div className="flex items-center gap-2 text-youtube">
        <HelpCircle className="h-4 w-4" />
        <span className="text-xs font-bold uppercase tracking-wider">Quiz</span>
      </div>
      <div className="space-y-3">
        {quiz.map((item, i) => (
          <div
            key={i}
            className="rounded-md border border-white/10 bg-black/20 p-3"
          >
            <p className="text-sm font-medium text-foreground">{item.question}</p>
            <p className="mt-1 text-sm text-muted-foreground">{item.answer}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChaptersList({ chapters }: { chapters: ChapterItem[] }) {
  return (
    <div className="space-y-3 rounded-lg border border-youtube/30 bg-youtube/5 p-4">
      <div className="flex items-center gap-2 text-youtube">
        <List className="h-4 w-4" />
        <span className="text-xs font-bold uppercase tracking-wider">Chapters</span>
      </div>
      <ol className="space-y-1">
        {chapters.map((chapter, i) => (
          <li
            key={i}
            className="group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground"
          >
            <Clock className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="font-mono text-xs text-muted-foreground">
              {formatTimestamp(chapter.timestamp)}
            </span>
            <span className="flex-1">{chapter.title}</span>
            <CopyButton text={chapter.title} />
          </li>
        ))}
      </ol>
    </div>
  );
}

function ShortsLinkBadge({ shortsLink }: { shortsLink: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-youtube/30 bg-youtube/5 px-3 py-2">
      <Play className="h-3 w-3 fill-current text-youtube" />
      <span className="text-xs text-muted-foreground">Related Short:</span>
      <span className="text-xs font-medium text-foreground">{shortsLink}</span>
    </div>
  );
}

export default function YouTubeLongFormPreview({
  chapters,
  poll,
  quiz,
  thumbnailBriefs,
  shortsLink,
}: YouTubeLongFormPreviewProps) {
  const hasFeatures =
    (chapters && chapters.length > 0) ||
    poll ||
    (quiz && quiz.length > 0) ||
    (thumbnailBriefs && thumbnailBriefs.length > 0) ||
    shortsLink;

  if (!hasFeatures) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-xl border-2 border-dashed border-youtube/30 bg-youtube/5">
        <p className="text-center text-sm text-muted-foreground">
          Generate adaptation to preview
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-youtube">
        <Play className="h-4 w-4 fill-current" />
        <span className="text-xs font-bold uppercase tracking-wider">YouTube Video</span>
      </div>

      <div className="space-y-3">
        {poll && <PollCard poll={poll} />}
        {quiz && quiz.length > 0 && <QuizCard quiz={quiz} />}
        {chapters && chapters.length > 0 && <ChaptersList chapters={chapters} />}
        {shortsLink && <ShortsLinkBadge shortsLink={shortsLink} />}
      </div>
    </div>
  );
}
