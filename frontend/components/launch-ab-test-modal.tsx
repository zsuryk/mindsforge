"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Rocket, X } from "lucide-react";
import Link from "next/link";

import {
  AbExperimentVariantKind,
  AdaptationThumbnailVariant,
  mediaUrl,
  startAbTest,
} from "@/lib/api";
import { EXPERIMENT_PLATFORMS } from "@/lib/platforms";

const EMPTY_TITLES: string[] = [];
const EMPTY_VARIANTS: AdaptationThumbnailVariant[] = [];

export default function LaunchAbTestModal({
  open,
  onClose,
  clipId,
  suggestedTitles = EMPTY_TITLES,
  variantKind = AbExperimentVariantKind.TITLE,
  thumbnailVariants = EMPTY_VARIANTS,
  platform: initialPlatform = "youtube_shorts",
}: {
  open: boolean;
  onClose: () => void;
  clipId: string;
  suggestedTitles: string[];
  variantKind?: AbExperimentVariantKind;
  thumbnailVariants?: AdaptationThumbnailVariant[];
  platform?: string;
}) {
  const [platform, setPlatform] = useState<string>(initialPlatform);
  const [kind, setKind] = useState<AbExperimentVariantKind>(variantKind);
  const [selected, setSelected] = useState<string[]>(suggestedTitles);
  const [selectedThumbs, setSelectedThumbs] = useState<string[]>(
    thumbnailVariants.map((variant) => variant.id),
  );
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const [launchedId, setLaunchedId] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setPlatform(initialPlatform);
      setKind(variantKind);
      setSelected(suggestedTitles);
      setSelectedThumbs(thumbnailVariants.map((variant) => variant.id));
      setLaunching(false);
      setLaunchError(null);
      setLaunchedId(null);
    }
  }, [open, variantKind, thumbnailVariants, suggestedTitles, initialPlatform]);

  if (!open) return null;

  const thumbnailMode = kind === AbExperimentVariantKind.THUMBNAIL;
  const usableThumbs = thumbnailMode
    ? thumbnailVariants.filter((variant) => variant.file_path)
    : [];

  const toggleTitle = (title: string) => {
    setSelected((current) =>
      current.includes(title)
        ? current.filter((t) => t !== title)
        : [...current, title],
    );
  };

  const toggleThumb = (id: string) => {
    setSelectedThumbs((current) =>
      current.includes(id)
        ? current.filter((t) => t !== id)
        : [...current, id],
    );
  };

  const canLaunch =
    !launching &&
    (thumbnailMode
      ? usableThumbs.length >= 2 && selectedThumbs.length >= 2
      : selected.length >= 2);

  const handleLaunch = async () => {
    setLaunching(true);
    setLaunchError(null);
    try {
      const pickedThumbs = thumbnailMode
        ? thumbnailVariants.filter((variant) => selectedThumbs.includes(variant.id))
        : [];
      const titles = thumbnailMode
        ? pickedThumbs.map((variant) => variant.overlay_text || variant.id)
        : selected;
      const experiment = await startAbTest({
        clipId,
        platform,
        titles,
        variantKind: thumbnailMode
          ? AbExperimentVariantKind.THUMBNAIL
          : AbExperimentVariantKind.TITLE,
        thumbnailPaths: thumbnailMode
          ? pickedThumbs.map((variant) => variant.file_path ?? "")
          : [],
      });
      setLaunchedId(experiment.id);
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : "Failed to launch A/B test");
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Launch A/B test"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-edge-strong bg-card p-6 shadow-2xl shadow-black/40"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-accent" />
            <h2 className="font-display text-lg font-semibold text-fg">Launch A/B Test</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="rounded-md p-1 text-muted transition-colors hover:bg-elevated hover:text-fg"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {launchedId === null ? (
          <>
            <label
              className="mb-1 block text-sm font-medium text-muted"
              htmlFor="ab-platform"
            >
              Platform
            </label>
            <select
              id="ab-platform"
              value={platform}
              onChange={(event) => setPlatform(event.target.value)}
              className="mb-4 w-full rounded-lg border border-edge-strong bg-background px-3 py-2 text-sm text-fg focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
            >
              {EXPERIMENT_PLATFORMS.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>

            {thumbnailVariants.length >= 2 && (
              <div className="mb-4 flex gap-1 rounded-lg border border-edge bg-background p-1">
                <button
                  type="button"
                  onClick={() => setKind(AbExperimentVariantKind.TITLE)}
                  aria-selected={!thumbnailMode}
                  className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    !thumbnailMode
                      ? "bg-accent text-accent-foreground"
                      : "text-muted hover:text-fg"
                  }`}
                >
                  Title variants
                </button>
                <button
                  type="button"
                  onClick={() => setKind(AbExperimentVariantKind.THUMBNAIL)}
                  aria-selected={thumbnailMode}
                  className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    thumbnailMode
                      ? "bg-accent text-accent-foreground"
                      : "text-muted hover:text-fg"
                  }`}
                >
                  Thumbnail variants
                </button>
              </div>
            )}

            {thumbnailMode ? (
              <fieldset className="mb-4">
                <legend className="mb-2 text-sm font-medium text-muted">
                  Variants (rendered thumbnails)
                </legend>
                {usableThumbs.length === 0 ? (
                  <p className="text-sm text-subtle">No rendered thumbnails yet.</p>
                ) : (
                  <div className="space-y-2">
                    {usableThumbs.map((variant) => (
                      <label
                        key={variant.id}
                        className="flex cursor-pointer items-center gap-3 rounded-lg border border-edge bg-background p-2.5 text-sm text-fg transition-colors hover:border-edge-strong"
                      >
                        <input
                          type="checkbox"
                          checked={selectedThumbs.includes(variant.id)}
                          onChange={() => toggleThumb(variant.id)}
                          className="accent-accent"
                        />
                        <img
                          src={mediaUrl(variant.url)}
                          alt={variant.overlay_text || variant.id}
                          className="h-12 w-20 shrink-0 rounded-md object-cover"
                        />
                        <span className="leading-snug">
                          {variant.overlay_text || variant.id}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </fieldset>
            ) : (
              <fieldset className="mb-4">
                <legend className="mb-2 text-sm font-medium text-muted">
                  Variants (titles)
                </legend>
                <div className="space-y-2">
                  {suggestedTitles.length === 0 ? (
                    <p className="text-sm text-subtle">No suggested titles yet.</p>
                  ) : (
                    suggestedTitles.map((title) => (
                      <label
                        key={title}
                        className="flex cursor-pointer items-start gap-2 rounded-lg border border-edge bg-background p-3 text-sm text-fg transition-colors hover:border-edge-strong"
                      >
                        <input
                          type="checkbox"
                          checked={selected.includes(title)}
                          onChange={() => toggleTitle(title)}
                          className="mt-0.5 accent-accent"
                        />
                        <span className="leading-snug">{title}</span>
                      </label>
                    ))
                  )}
                </div>
              </fieldset>
            )}

            <button
              onClick={handleLaunch}
              disabled={!canLaunch}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Rocket className="h-4 w-4" />
              {launching ? "Launching…" : "Launch"}
            </button>

            {launchError && (
              <p className="mt-3 text-center text-xs text-red-400">{launchError}</p>
            )}
          </>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-300">
              A/B test launched! The worker is now gathering views. The winning variant
              and its insight will be recorded once the test concludes.
            </div>
            <Link
              href="/ab-experiments"
              onClick={onClose}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground transition-colors hover:bg-accent-hover"
            >
              <FlaskConical className="h-4 w-4" />
              Track it on the experiments page
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
