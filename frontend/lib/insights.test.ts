import { describe, expect, it } from "vitest";

import { collectInsights } from "./insights";

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
      { title: "A/B insight · v2", detail: "question hooks win" },
    ]);
  });

  it("extracts structured learned insights and falls back to numbering", () => {
    const insights = collectInsights({
      ab_test_history: [{ learned_insight: { ctr: 0.04 } }, { winning_variant_id: "v1" }],
    });

    expect(insights[0]).toEqual({ title: "A/B insight #1", detail: '{"ctr":0.04}' });
    expect(insights).toHaveLength(1);
  });

  it("ignores entries without insight content", () => {
    expect(collectInsights({ ab_test_history: [{ winning_variant_id: "v1" }] })).toEqual([]);
    expect(collectInsights({ ab_test_history: [42, null] })).toEqual([]);
  });
});
