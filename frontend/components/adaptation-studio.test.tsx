import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import AdaptationStudio from "./adaptation-studio";
import { Adaptation } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeReadyAdaptation(): Adaptation {
  return {
    id: "adapt-1",
    clip_id: "clip-1",
    platform: "youtube",
    surface: "SHORTS",
    status: "READY",
    features: {
      chapters: [{ title: "The hook", timestamp: 2.0 }],
      tags: ["editing", "storytime"],
      poll: { question: "Which ending?", options: ["A", "B"] },
      quiz: [{ question: "What changed?", answer: "Everything" }],
      thumbnail_briefs: [
        { frame_timestamp: 1.0, overlay_text: "Wait for it" },
        { frame_timestamp: 2.0, overlay_text: "The reveal" },
        { frame_timestamp: 3.0, overlay_text: "You won't believe" },
      ],
      platform_hooks: ["Wait for the twist"],
    },
    assets: {
      thumbnail_variants: [
        {
          id: "thumb_1",
          frame_timestamp: 1.0,
          overlay_text: "Wait for it",
          file_path: "/tmp/media/adaptations/adapt-1/thumb_1.png",
          url: "/media/adaptations/adapt-1/thumb_1.png",
        },
        {
          id: "thumb_2",
          frame_timestamp: 2.0,
          overlay_text: "The reveal",
          file_path: "/tmp/media/adaptations/adapt-1/thumb_2.png",
          url: "/media/adaptations/adapt-1/thumb_2.png",
        },
        {
          id: "thumb_3",
          frame_timestamp: 3.0,
          overlay_text: "You won't believe",
          file_path: "/tmp/media/adaptations/adapt-1/thumb_3.png",
          url: "/media/adaptations/adapt-1/thumb_3.png",
        },
      ],
      captions_url: "/media/adaptations/adapt-1/captions.srt",
      chapters_url: null,
    },
    error_message: null,
    created_at: "2026-08-13T10:00:00Z",
    updated_at: "2026-08-13T10:00:00Z",
  };
}

function stubFetch(adaptations: Adaptation[] = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/adaptations") && !url.endsWith("/adaptations")) {
        return Promise.resolve(jsonResponse(adaptations[0]));
      }
      return Promise.resolve(jsonResponse(adaptations));
    }),
  );
}

function stubFetchForGenerate({
  created,
  ready,
}: {
  created: Adaptation;
  ready: Adaptation;
}) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse(created, 202));
      }
      if (url.includes("/adaptations/")) {
        return Promise.resolve(jsonResponse(ready));
      }
      return Promise.resolve(jsonResponse([]));
    }),
  );
  return calls;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdaptationStudio", () => {
  it("shows the target tabs and an ungenerated state", async () => {
    stubFetch();
    render(<AdaptationStudio clipId="clip-1" />);

    expect(await screen.findByText("Adaptation studio")).toBeInTheDocument();
    for (const tab of ["YouTube Shorts", "YouTube Video", "TikTok", "X"]) {
      expect(screen.getByRole("button", { name: tab })).toBeInTheDocument();
    }
    expect(
      screen.getByText(/no adaptation generated for youtube shorts yet/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate/i })).toBeInTheDocument();
  });

  it("generates, polls to READY and renders manifest, assets and checklist", async () => {
    const user = userEvent.setup();
    const created = {
      ...makeReadyAdaptation(),
      status: "PENDING",
      features: null,
      assets: null,
    } as unknown as Adaptation;
    stubFetchForGenerate({ created, ready: makeReadyAdaptation() });

    render(<AdaptationStudio clipId="clip-1" />);

    await user.click(await screen.findByRole("button", { name: /generate/i }));

    expect(await screen.findByText("READY")).toBeInTheDocument();

    expect(await screen.findByText("The hook — 0:02")).toBeInTheDocument();
    expect(screen.getByText(/Question: Which ending\?/)).toBeInTheDocument();
    expect(screen.getByText(/- A/)).toBeInTheDocument();
    expect(screen.getByText(/- B/)).toBeInTheDocument();
    expect(screen.getByText(/What changed\? — Everything/)).toBeInTheDocument();

    expect(screen.getByAltText("Thumbnail: Wait for it")).toHaveAttribute(
      "src",
      "http://localhost:8000/media/adaptations/adapt-1/thumb_1.png",
    );
    expect(screen.getByText("captions.srt")).toBeInTheDocument();
    expect(screen.queryByText("chapters.txt")).not.toBeInTheDocument();

    expect(screen.getByText("Run Test & Compare")).toBeInTheDocument();

    const checklist = screen.getByText("Publish checklist").closest("div") as HTMLElement;
    const step = within(checklist).getByRole("checkbox", {
      name: /upload the short/i,
    });
    await user.click(step);
    expect(step).toBeChecked();
  });

  it("copies a manifest panel to the clipboard", async () => {
    const user = userEvent.setup();
    stubFetch([makeReadyAdaptation()]);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(<AdaptationStudio clipId="clip-1" />);

    await user.click(await screen.findByRole("button", { name: "Copy Chapters" }));

    expect(writeText).toHaveBeenCalledWith("The hook — 0:02");
  });

  it("shows the failure state with the error message", async () => {
    const user = userEvent.setup();
    const failed = {
      ...makeReadyAdaptation(),
      status: "FAILED",
      features: null,
      assets: null,
      error_message: "builder api down",
    } as unknown as Adaptation;
    const created = {
      ...failed,
      status: "PENDING",
    } as unknown as Adaptation;
    stubFetchForGenerate({ created, ready: failed });

    render(<AdaptationStudio clipId="clip-1" />);

    await user.click(await screen.findByRole("button", { name: /generate/i }));

    expect(await screen.findByText("FAILED")).toBeInTheDocument();
    expect(screen.getByText("builder api down")).toBeInTheDocument();
  });

  it("launches a thumbnail A/B test with the rendered variants", async () => {
    const user = userEvent.setup();
    stubFetch([makeReadyAdaptation()]);
    const created = {
      id: "exp-1",
      clip_id: "clip-1",
      clip_title: "Clip",
      platform: "youtube_shorts",
      variant_kind: "THUMBNAIL",
      status: "ACTIVE",
      variants: [],
      winning_variant_id: null,
      learned_insight: null,
      created_at: "2026-08-13T10:00:00Z",
      concluded_at: null,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/ab-tests/start")) {
        return Promise.resolve(jsonResponse(created, 201));
      }
      if (url.includes("/adaptations")) {
        return Promise.resolve(jsonResponse([makeReadyAdaptation()]));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AdaptationStudio clipId="clip-1" />);

    await user.click(await screen.findByRole("button", { name: /run test & compare/i }));

    const dialog = screen.getByRole("dialog", { name: "Launch A/B test" });
    expect(within(dialog).getByText("Thumbnail variants")).toBeInTheDocument();
    expect(within(dialog).getByText("Wait for it")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Launch" }));

    expect(
      await within(dialog).findByText(/a\/b test launched/i),
    ).toBeInTheDocument();

    const [, init] = fetchMock.mock.calls.find(([callUrl]) =>
      String(callUrl).includes("/ab-tests/start"),
    ) as unknown as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body.variant_kind).toBe("THUMBNAIL");
    expect(body.thumbnail_paths).toHaveLength(3);
    expect(body.thumbnail_paths[0]).toContain("thumb_1.png");
    expect(body.titles).toEqual(["Wait for it", "The reveal", "You won't believe"]);
  });
});