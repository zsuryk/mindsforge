"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Rocket, X } from "lucide-react";
import Link from "next/link";

import { startAbTest } from "@/lib/api";
import { PLATFORMS } from "@/lib/platforms";

export default function LaunchAbTestModal({
  open,
  onClose,
  clipId,
  suggestedTitles,
}: {
  open: boolean;
  onClose: () => void;
  clipId: string;
  suggestedTitles: string[];
}) {
  const [platform, setPlatform] = useState<string>("youtube_shorts");
  const [selected, setSelected] = useState<string[]>(suggestedTitles);
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const [launchedId, setLaunchedId] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setPlatform("youtube_shorts");
      setSelected(suggestedTitles);
      setLaunching(false);
      setLaunchError(null);
      setLaunchedId(null);
    }
  }, [open, suggestedTitles]);

  if (!open) return null;

  const toggleTitle = (title: string) => {
    setSelected((current) =>
      current.includes(title)
        ? current.filter((t) => t !== title)
        : [...current, title],
    );
  };

  const handleLaunch = async () => {
    setLaunching(true);
    setLaunchError(null);
    try {
      const experiment = await startAbTest({ clipId, platform, titles: selected });
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-indigo-400" />
            <h2 className="text-lg font-semibold text-slate-100">Launch A/B Test</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {launchedId === null ? (
          <>
            <label
              className="mb-1 block text-sm font-medium text-slate-300"
              htmlFor="ab-platform"
            >
              Platform
            </label>
            <select
              id="ab-platform"
              value={platform}
              onChange={(event) => setPlatform(event.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none"
            >
              {PLATFORMS.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>

            <fieldset className="mb-4">
              <legend className="mb-2 text-sm font-medium text-slate-300">
                Variants (titles)
              </legend>
              <div className="space-y-2">
                {suggestedTitles.length === 0 ? (
                  <p className="text-sm text-slate-500">No suggested titles yet.</p>
                ) : (
                  suggestedTitles.map((title) => (
                    <label
                      key={title}
                      className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm text-slate-200 hover:border-slate-700"
                    >
                      <input
                        type="checkbox"
                        checked={selected.includes(title)}
                        onChange={() => toggleTitle(title)}
                        className="mt-0.5 accent-indigo-500"
                      />
                      <span className="leading-snug">{title}</span>
                    </label>
                  ))
                )}
              </div>
            </fieldset>

            <button
              onClick={handleLaunch}
              disabled={selected.length < 2 || launching}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
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
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400"
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
