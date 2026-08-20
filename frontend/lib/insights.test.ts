import { describe, expect, it } from "vitest";

import {
  collectBrandRules,
  collectInsights,
  collectLatestInsights,
  collectTrendQueries,
} from "./insights";

describe("collectInsights", () => {
  it("returns an empty list for an empty memory", () => {
    expect(collectInsights({})).toEqual([]);
  });

  it("extracts the brand voice", () => {
    expect(collectInsights({ brand_voice: "bold" })).toEqual([
      { title: "Brand voice", detail: "bold" },
    ]);
  });

  it("extracts one card per historical platform item", () => {
    const insights = collectInsights({
      historical_insights: {
        tiktok: ["fast pacing", "captions on"],
        youtube: ["hook in first 3s"],
      },
    });

    expect(insights).toEqual([
      { title: "Tiktok insight", detail: "fast pacing" },
      { title: "Tiktok insight", detail: "captions on" },
      { title: "Youtube insight", detail: "hook in first 3s" },
    ]);
  });

  it("stringifies structured historical items", () => {
    const insights = collectInsights({
      historical_insights: {
        youtube: [{ titles: ["A"], duration: 30 }],
      },
    });

    expect(insights[0].detail).toBe('{"titles":["A"],"duration":30}');
  });

  it("extracts learned insights from ab test history with winner", () => {
    const insights = collectInsights({
      ab_test_history: [
        { winning_variant_id: "v2", learned_insight: "question hooks win" },
      ],
    });

    expect(insights).toEqual([
      { title: "A/B insight · v2", detail: "question hooks win", created_at: null },
    ]);
  });

  it("extracts structured learned insights and falls back to numbering", () => {
    const insights = collectInsights({
      ab_test_history: [{ learned_insight: { ctr: 0.04 } }, { winning_variant_id: "v1" }],
    });

    expect(insights[0]).toEqual({
      title: "A/B insight #1",
      detail: '{"ctr":0.04}',
      created_at: null,
    });
    expect(insights).toHaveLength(1);
  });

  it("ignores entries without insight content", () => {
    expect(collectInsights({ ab_test_history: [{ winning_variant_id: "v1" }] })).toEqual([]);
    expect(collectInsights({ ab_test_history: [42, null] })).toEqual([]);
  });

  it("carries the concluded_at timestamp on A/B insights", () => {
    const insights = collectInsights({
      ab_test_history: [
        {
          winning_variant_id: "v2",
          learned_insight: "question hooks win",
          concluded_at: "2026-08-19T10:00:00Z",
        },
      ],
    });

    expect(insights[0].created_at).toBe("2026-08-19T10:00:00Z");
  });
});

describe("collectBrandRules", () => {
  it("returns an empty list when memory has no rules", () => {
    expect(collectBrandRules({})).toEqual([]);
    expect(collectBrandRules({ brand_rules: "nope" })).toEqual([]);
  });

  it("returns the latest 3 rules newest-first with timestamps", () => {
    const rules = collectBrandRules({
      brand_rules: [
        { text: "oldest", created_at: "2026-08-01T10:00:00Z" },
        { text: "middle", created_at: "2026-08-10T10:00:00Z" },
        { text: "newest", created_at: "2026-08-19T10:00:00Z" },
        { text: "latest", created_at: "2026-08-20T10:00:00Z" },
      ],
    });

    expect(rules).toEqual([
      { text: "latest", created_at: "2026-08-20T10:00:00Z" },
      { text: "newest", created_at: "2026-08-19T10:00:00Z" },
      { text: "middle", created_at: "2026-08-10T10:00:00Z" },
    ]);
  });

  it("drops entries without text and renders without a timestamp", () => {
    const rules = collectBrandRules({
      brand_rules: [
        { text: "  always bold captions  ", created_at: "2026-08-19T10:00:00Z" },
        { text: "" },
        { text: "no timestamp" },
        { not_text: true },
      ],
    });

    expect(rules).toEqual([
      { text: "no timestamp", created_at: null },
      { text: "always bold captions", created_at: "2026-08-19T10:00:00Z" },
    ]);
  });
});

describe("collectTrendQueries", () => {
  it("returns an empty list when memory has no trend research", () => {
    expect(collectTrendQueries({})).toEqual([]);
  });

  it("returns the latest 2 queries newest-first with timestamps", () => {
    const trends = collectTrendQueries({
      trend_research: [
        { query: "oldest", researched_at: "2026-08-01T10:00:00Z" },
        { query: "middle", researched_at: "2026-08-10T10:00:00Z" },
        { query: "newest", researched_at: "2026-08-19T10:00:00Z" },
      ],
    });

    expect(trends).toEqual([
      { query: "newest", researched_at: "2026-08-19T10:00:00Z" },
      { query: "middle", researched_at: "2026-08-10T10:00:00Z" },
    ]);
  });

  it("drops entries without a query", () => {
    const trends = collectTrendQueries({
      trend_research: [
        { query: "", researched_at: "2026-08-19T10:00:00Z" },
        { query: "  viral hooks  ", researched_at: null },
      ],
    });

    expect(trends).toEqual([{ query: "viral hooks", researched_at: null }]);
  });
});

describe("collectLatestInsights", () => {
  it("excludes the brand voice and sorts A/B insights newest-first", () => {
    const insights = collectLatestInsights({
      brand_voice: "bold and direct",
      ab_test_history: [
        {
          winning_variant_id: "v1",
          learned_insight: "older lesson",
          concluded_at: "2026-08-01T10:00:00Z",
        },
        {
          winning_variant_id: "v2",
          learned_insight: "fresher lesson",
          concluded_at: "2026-08-19T10:00:00Z",
        },
      ],
    });

    expect(insights).toEqual([
      { title: "A/B insight · v2", detail: "fresher lesson", created_at: "2026-08-19T10:00:00Z" },
      { title: "A/B insight · v1", detail: "older lesson", created_at: "2026-08-01T10:00:00Z" },
    ]);
  });

  it("returns at most 3 insights", () => {
    const memory = {
      ab_test_history: [1, 2, 3, 4].map((index) => ({
        winning_variant_id: `v${index}`,
        learned_insight: `lesson ${index}`,
        concluded_at: `2026-08-0${index}T10:00:00Z`,
      })),
    };

    expect(collectLatestInsights(memory)).toHaveLength(3);
    expect(collectLatestInsights(memory)[0].detail).toBe("lesson 4");
  });

  it("keeps untimestamped insights when there are fewer than 3 timestamped ones", () => {
    const insights = collectLatestInsights({
      historical_insights: { tiktok: ["fast pacing"] },
    });

    expect(insights).toEqual([{ title: "Tiktok insight", detail: "fast pacing" }]);
  });
});
