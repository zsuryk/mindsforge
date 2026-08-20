export type Insight = {
  title: string;
  detail: string;
  created_at?: string | null;
};

export type BrandRuleEntry = {
  text: string;
  created_at: string | null;
};

export type TrendResearchEntry = {
  query: string;
  researched_at: string | null;
};

export const BRAND_VOICE_TITLE = "Brand voice";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringify(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function platformLabel(platform: string): string {
  return platform
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

function timestampMs(value: string | null | undefined): number {
  if (typeof value !== "string" || !value) return 0;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? 0 : ms;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function collectBrandRules(
  memory: Record<string, unknown>,
  limit = 3,
): BrandRuleEntry[] {
  const rules = memory.brand_rules;
  if (!Array.isArray(rules)) return [];
  const entries: BrandRuleEntry[] = [];
  for (const rule of rules) {
    if (!isRecord(rule)) continue;
    const text = typeof rule.text === "string" ? rule.text.trim() : "";
    if (!text) continue;
    entries.push({ text, created_at: stringOrNull(rule.created_at) });
  }
  return entries.slice(-limit).reverse();
}

export function collectTrendQueries(
  memory: Record<string, unknown>,
  limit = 2,
): TrendResearchEntry[] {
  const history = memory.trend_research;
  if (!Array.isArray(history)) return [];
  const entries: TrendResearchEntry[] = [];
  for (const entry of history) {
    if (!isRecord(entry)) continue;
    const query = typeof entry.query === "string" ? entry.query.trim() : "";
    if (!query) continue;
    entries.push({ query, researched_at: stringOrNull(entry.researched_at) });
  }
  return entries.slice(-limit).reverse();
}

export function collectLatestInsights(
  memory: Record<string, unknown>,
  limit = 3,
): Insight[] {
  return collectInsights(memory)
    .filter((insight) => insight.title !== BRAND_VOICE_TITLE)
    .sort(
      (a, b) => timestampMs(b.created_at) - timestampMs(a.created_at),
    )
    .slice(0, limit);
}

export function collectInsights(memory: Record<string, unknown>): Insight[] {
  const insights: Insight[] = [];

  const brandVoice = memory.brand_voice;
  if (typeof brandVoice === "string" && brandVoice.trim()) {
    insights.push({ title: BRAND_VOICE_TITLE, detail: brandVoice });
  }

  const historical = memory.historical_insights;
  if (isRecord(historical)) {
    for (const [platform, value] of Object.entries(historical)) {
      const items = Array.isArray(value) ? value : [];
      for (const item of items) {
        const detail = stringify(item);
        if (detail.trim()) {
          insights.push({ title: `${platformLabel(platform)} insight`, detail });
        }
      }
    }
  }

  const history = memory.ab_test_history;
  if (Array.isArray(history)) {
    history.forEach((entry, index) => {
      if (!isRecord(entry)) return;
      const detail = stringify(entry.learned_insight ?? null);
      const winner = typeof entry.winning_variant_id === "string"
        ? entry.winning_variant_id
        : null;
      if (detail !== "null" && detail.trim()) {
        insights.push({
          title: winner ? `A/B insight · ${winner}` : `A/B insight #${index + 1}`,
          detail,
          created_at: stringOrNull(entry.concluded_at),
        });
      }
    });
  }

  return insights;
}
