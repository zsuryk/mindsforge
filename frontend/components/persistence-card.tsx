import { useCallback, useEffect, useState } from "react";
import {
  ArrowUpRight,
  BookMarked,
  Brain,
  Lightbulb,
  Quote,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchAgentMemory } from "@/lib/api";
import {
  collectBrandRules,
  collectLatestInsights,
  collectTrendQueries,
  isRecord,
} from "@/lib/insights";
import { formatRelativeTime } from "@/lib/utils";

const POLL_INTERVAL_MS = 5_000;
const BRAND_VOICE_EXCERPT_CHARS = 120;

function MemoryRow({
  icon: Icon,
  text,
  created_at,
  now,
  testId,
}: {
  icon: typeof Brain;
  text: string;
  created_at: string | null;
  now: number;
  testId: string;
}) {
  return (
    <li data-testid={testId} className="flex items-start gap-3 py-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/40 bg-secondary/50">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <p className="min-w-0 flex-1 break-words text-sm text-foreground">{text}</p>
      {created_at && (
        <span className="shrink-0 text-xs text-muted-foreground">
          {formatRelativeTime(created_at, now)}
        </span>
      )}
    </li>
  );
}

function EmptyRow({ children }: { children: React.ReactNode }) {
  return (
    <li className="py-3 text-sm text-muted-foreground">
      <span className="text-xs italic">{children}</span>
    </li>
  );
}

export function PersistenceCard() {
  const [memory, setMemory] = useState<Record<string, unknown> | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  const load = useCallback(async () => {
    try {
      const agentMemory = await fetchAgentMemory();
      setMemory(
        agentMemory && isRecord(agentMemory.memory) ? agentMemory.memory : {},
      );
      setUnavailable(false);
    } catch {
      setUnavailable(true);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const data = memory ?? {};
  const now = Date.now();

  const brandVoice =
    typeof data.brand_voice === "string" && data.brand_voice.trim()
      ? data.brand_voice.trim()
      : null;
  const brandVoiceExcerpt = brandVoice
    ? brandVoice.length > BRAND_VOICE_EXCERPT_CHARS
      ? `${brandVoice.slice(0, BRAND_VOICE_EXCERPT_CHARS)}…`
      : brandVoice
    : null;
  const brandRules = collectBrandRules(data);
  const insights = collectLatestInsights(data);
  const trends = collectTrendQueries(data);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 p-6 pb-4">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Brain className="h-4 w-4 text-mind" />
          What your Mind remembers
        </CardTitle>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/memory-inspector">
            See full memory
            <ArrowUpRight />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="p-0">
        {unavailable ? (
          <p className="px-6 pb-6 text-sm text-muted-foreground">
            Memory is unavailable right now — check the Mind configuration.
          </p>
        ) : memory === null ? (
          <p className="px-6 pb-6 text-sm text-muted-foreground">
            Loading memory…
          </p>
        ) : (
          <div className="grid gap-x-8 px-6 pb-2 lg:grid-cols-4">
            <section className="pb-4">
              <h3 className="flex items-center gap-1.5 pt-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <Quote className="h-3.5 w-3.5" /> Brand voice
              </h3>
              {brandVoiceExcerpt ? (
                <MemoryRow
                  testId="recap-brand-voice"
                  icon={Quote}
                  text={brandVoiceExcerpt}
                  created_at={null}
                  now={now}
                />
              ) : (
                <EmptyRow>No brand voice yet — state it in chat.</EmptyRow>
              )}
            </section>

            <section className="pb-4">
              <h3 className="flex items-center gap-1.5 pt-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <BookMarked className="h-3.5 w-3.5" /> Brand rules
              </h3>
              {brandRules.length === 0 ? (
                <EmptyRow>No brand rules yet — chat your preferences.</EmptyRow>
              ) : (
                <ul className="divide-y divide-border/40">
                  {brandRules.map((rule) => (
                    <MemoryRow
                      key={`${rule.created_at}-${rule.text}`}
                      testId="recap-brand-rule"
                      icon={BookMarked}
                      text={rule.text}
                      created_at={rule.created_at}
                      now={now}
                    />
                  ))}
                </ul>
              )}
            </section>

            <section className="pb-4">
              <h3 className="flex items-center gap-1.5 pt-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <Lightbulb className="h-3.5 w-3.5" /> Learned insights
              </h3>
              {insights.length === 0 ? (
                <EmptyRow>No learned insights yet — run an A/B test.</EmptyRow>
              ) : (
                <ul className="divide-y divide-border/40">
                  {insights.map((insight, index) => (
                    <MemoryRow
                      key={`${insight.title}-${index}`}
                      testId="recap-insight"
                      icon={Lightbulb}
                      text={insight.detail}
                      created_at={insight.created_at ?? null}
                      now={now}
                    />
                  ))}
                </ul>
              )}
            </section>

            <section className="pb-4">
              <h3 className="flex items-center gap-1.5 pt-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <TrendingUp className="h-3.5 w-3.5" /> Trend research
              </h3>
              {trends.length === 0 ? (
                <EmptyRow>No trend research yet — ask in chat.</EmptyRow>
              ) : (
                <ul className="divide-y divide-border/40">
                  {trends.map((trend) => (
                    <MemoryRow
                      key={`${trend.researched_at}-${trend.query}`}
                      testId="recap-trend"
                      icon={TrendingUp}
                      text={trend.query}
                      created_at={trend.researched_at}
                      now={now}
                    />
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </CardContent>
    </Card>
  );
}