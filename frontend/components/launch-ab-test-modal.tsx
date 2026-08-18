"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Rocket } from "lucide-react";
import Link from "next/link";

import {
  AbExperimentVariantKind,
  AdaptationThumbnailVariant,
  mediaUrl,
  startAbTest,
} from "@/lib/api";
import { EXPERIMENT_PLATFORMS } from "@/lib/platforms";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

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
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-muted-foreground" />
            Launch A/B Test
          </DialogTitle>
          <DialogDescription>
            Pick the variants to run — the winner is written to memory once the test
            concludes.
          </DialogDescription>
        </DialogHeader>

        {launchedId === null ? (
          <div className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="ab-platform">Platform</Label>
              <Select
                id="ab-platform"
                value={platform}
                onChange={(event) => setPlatform(event.target.value)}
              >
                {EXPERIMENT_PLATFORMS.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>

            {thumbnailVariants.length >= 2 && (
              <Tabs
                value={kind}
                onValueChange={(next) =>
                  setKind(next as AbExperimentVariantKind)
                }
              >
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value={AbExperimentVariantKind.TITLE}>
                    Title variants
                  </TabsTrigger>
                  <TabsTrigger value={AbExperimentVariantKind.THUMBNAIL}>
                    Thumbnail variants
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            )}

            {thumbnailMode ? (
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium text-muted-foreground">
                  Variants (rendered thumbnails)
                </legend>
                {usableThumbs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No rendered thumbnails yet.</p>
                ) : (
                  <div className="space-y-2">
                    {usableThumbs.map((variant) => (
                      <label
                        key={variant.id}
                        className="flex cursor-pointer items-center gap-3 rounded-lg border border-border/40 bg-background/60 p-2.5 text-sm text-foreground transition-colors hover:border-border"
                      >
                        <input
                          type="checkbox"
                          checked={selectedThumbs.includes(variant.id)}
                          onChange={() => toggleThumb(variant.id)}
                          className="size-4 accent-primary"
                        />
                        <img
                          src={mediaUrl(variant.url)}
                          alt={variant.overlay_text || variant.id}
                          className="h-12 w-20 shrink-0 rounded-md border border-border/40 object-cover"
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
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium text-muted-foreground">
                  Variants (titles)
                </legend>
                <div className="space-y-2">
                  {suggestedTitles.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No suggested titles yet.</p>
                  ) : (
                    suggestedTitles.map((title) => (
                      <label
                        key={title}
                        className="flex cursor-pointer items-start gap-2 rounded-lg border border-border/40 bg-background/60 p-3 text-sm text-foreground transition-colors hover:border-border"
                      >
                        <input
                          type="checkbox"
                          checked={selected.includes(title)}
                          onChange={() => toggleTitle(title)}
                          className="mt-0.5 size-4 accent-primary"
                        />
                        <span className="leading-snug">{title}</span>
                      </label>
                    ))
                  )}
                </div>
              </fieldset>
            )}

            <Button
              onClick={handleLaunch}
              disabled={!canLaunch}
              className="w-full"
              size="lg"
            >
              <Rocket />
              {launching ? "Launching…" : "Launch"}
            </Button>

            {launchError && (
              <p className="text-center text-xs text-destructive">{launchError}</p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-300">
              A/B test launched! The worker is now gathering views. The winning variant
              and its insight will be recorded once the test concludes.
            </div>
            <Button asChild className="w-full" size="lg">
              <Link href="/ab-experiments" onClick={onClose}>
                <FlaskConical />
                Track it on the experiments page
              </Link>
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
