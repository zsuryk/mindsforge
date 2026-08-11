import { PlatformHooks } from "@/lib/api";

export const PLATFORMS: { key: keyof PlatformHooks; label: string }[] = [
  { key: "youtube_shorts", label: "YouTube Shorts" },
  { key: "tiktok", label: "TikTok" },
  { key: "x", label: "X" },
];
