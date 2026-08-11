export type Insight = {
  title: string;
  detail: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
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

export function collectInsights(memory: Record<string, unknown>): Insight[] {
  const insights: Insight[] = [];

  const brandVoice = memory.brand_voice;
  if (typeof brandVoice === "string" && brandVoice.trim()) {
    insights.push({ title: "Brand voice", detail: brandVoice });
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
        });
      }
    });
  }

  return insights;
}
