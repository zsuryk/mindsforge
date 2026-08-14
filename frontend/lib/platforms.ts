import { PlatformHooks } from "@/lib/api";

// Platform-hooks vocabulary: short-form platforms the Mind authors hooks for.
export const PLATFORMS: { key: keyof PlatformHooks; label: string }[] = [
  { key: "youtube_shorts", label: "YouTube Shorts" },
  { key: "tiktok", label: "TikTok" },
  { key: "x", label: "X" },
];

// Experiment platform vocabulary: youtube covers long-form video tests.
export type ExperimentPlatformKey = "youtube_shorts" | "youtube" | "tiktok" | "x";

export const EXPERIMENT_PLATFORMS: { key: ExperimentPlatformKey; label: string }[] = [
  { key: "youtube_shorts", label: "YouTube Shorts" },
  { key: "youtube", label: "YouTube Video" },
  { key: "tiktok", label: "TikTok" },
  { key: "x", label: "X" },
];

export type AdaptationTarget = {
  platform: "youtube" | "tiktok" | "x";
  surface: "SHORTS" | "LONG_FORM" | "POST";
  label: string;
};

export const ADAPTATION_TARGETS: AdaptationTarget[] = [
  { platform: "youtube", surface: "SHORTS", label: "YouTube Shorts" },
  { platform: "youtube", surface: "LONG_FORM", label: "YouTube Video" },
  { platform: "tiktok", surface: "POST", label: "TikTok" },
  { platform: "x", surface: "POST", label: "X" },
];
