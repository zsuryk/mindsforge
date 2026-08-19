import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "clip-1" }),
}));

import ClipStudioPage from "../app/clips/[id]/page";
import { Adaptation, Clip } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubClipStudioFetch(clip: Clip, adaptations: Adaptation[] = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/adaptations")) {
        return Promise.resolve(jsonResponse(adaptations));
      }
      return Promise.resolve(jsonResponse(clip));
    }),
  );
}

function makeScoredClip(): Clip {
  return {
    id: "clip-1",
    job_id: "job-1",
    title: "The big reveal",
    start_time: 12.5,
    end_time: 42.0,
    transcript_text: "And here is the moment everyone has been waiting for.",
    video_url: "/media/clips/job-1/clip-1.mp4",
    thumbnail_url: "/media/clips/job-1/clip-1.png",
    virality_score: 78,
    suggested_hooks: {
      virality_score: 78,
      suggested_titles: ["The reveal you missed", "Why nobody talks about this", "Watch until the end"],
      platform_hooks: {
        youtube_shorts: ["Wait for the twist", "This changed everything"],
        tiktok: ["POV: you almost scrolled past", "Nobody told you this"],
        x: ["Hot take:", "Unpopular opinion:"],
      },
    },
    created_at: "2026-08-11T10:00:00Z",
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ClipStudioPage", () => {
  it("shows the loading state then the player and verdict", async () => {
    stubClipStudioFetch(makeScoredClip());

    const { container } = render(<ClipStudioPage />);

    expect(screen.getByText("Loading clip…")).toBeInTheDocument();

    expect(await screen.findByText("The big reveal")).toBeInTheDocument();
    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    expect(video).toHaveAttribute("src", "http://localhost:8000/media/clips/job-1/clip-1.mp4");
    expect(video).toHaveAttribute("poster", "http://localhost:8000/media/clips/job-1/clip-1.png");
    expect(screen.getByText("78")).toBeInTheDocument();
    expect(screen.getByText("High potential — ready to launch")).toBeInTheDocument();
  });

  it("renders a real scored clip with distinct per-platform hooks in tabs", async () => {
    const user = userEvent.setup();
    stubClipStudioFetch(makeScoredClip());

    render(<ClipStudioPage />);

    const hooksCard = await screen.findByRole("heading", { name: /platform hooks/i });
    const card = hooksCard.closest(".rounded-xl") as HTMLElement;

    expect(within(card).getByText("Wait for the twist")).toBeInTheDocument();

    await user.click(within(card).getByRole("tab", { name: "TikTok" }));
    expect(within(card).getByText("POV: you almost scrolled past")).toBeInTheDocument();
    expect(within(card).queryByText("Wait for the twist")).not.toBeInTheDocument();

    await user.click(within(card).getByRole("tab", { name: "X" }));
    expect(within(card).getByText("Hot take:")).toBeInTheDocument();
  });

  it("launches an A/B test from the modal and confirms", async () => {
    const user = userEvent.setup();
    const created = {
      id: "exp-1",
      clip_id: "clip-1",
      clip_title: "The big reveal",
      platform: "youtube_shorts",
      variant_kind: "TITLE",
      status: "ACTIVE",
      variants: [
        {
          variant_id: "v1",
          title: "The reveal you missed",
          thumbnail_url: "/media/clips/job-1/clip-1.png",
          ctr: 0,
          views: 0,
        },
        {
          variant_id: "v2",
          title: "Why nobody talks about this",
          thumbnail_url: "/media/clips/job-1/clip-1.png",
          ctr: 0,
          views: 0,
        },
      ],
      winning_variant_id: null,
      learned_insight: null,
      created_at: "2026-08-11T10:00:00Z",
      concluded_at: null,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/ab-tests/start")) {
        return Promise.resolve(jsonResponse(created, 201));
      }
      if (url.includes("/adaptations")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse(makeScoredClip()));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ClipStudioPage />);

    await user.click(await screen.findByRole("button", { name: /launch a\/b test/i }));

    const dialog = screen.getByRole("dialog", { name: /launch a\/b test/i });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("The reveal you missed")).toBeInTheDocument();
    expect(within(dialog).getByText("Why nobody talks about this")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Launch" }));

    expect(
      await within(dialog).findByText(/a\/b test launched/i),
    ).toBeInTheDocument();

    const [url, init] = fetchMock.mock.calls.find(
      ([callUrl]) => String(callUrl).includes("/ab-tests/start"),
    ) as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/ab-tests/start");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      clip_id: "clip-1",
      platform: "youtube_shorts",
      titles: ["The reveal you missed", "Why nobody talks about this", "Watch until the end"],
      variant_kind: "TITLE",
      thumbnail_paths: [],
    });
  });

  it("shows the launch error when the API rejects", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/ab-tests/start")) {
        return Promise.resolve(jsonResponse({ detail: "Clip not found" }, 404));
      }
      if (url.includes("/adaptations")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse(makeScoredClip()));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ClipStudioPage />);

    await user.click(await screen.findByRole("button", { name: /launch a\/b test/i }));
    const dialog = screen.getByRole("dialog", { name: /launch a\/b test/i });
    await user.click(within(dialog).getByRole("button", { name: "Launch" }));

    expect(await within(dialog).findByText("Clip not found")).toBeInTheDocument();
  });

  it("shows a pending state for unscored clips", async () => {
    const unscored: Clip = { ...makeScoredClip(), virality_score: null, suggested_hooks: null };
    stubClipStudioFetch(unscored);

    render(<ClipStudioPage />);

    expect(await screen.findByText(/no hooks yet/i)).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("caps the transcript in a scrollable pane", async () => {
    stubClipStudioFetch(makeScoredClip());

    render(<ClipStudioPage />);

    const paragraph = await screen.findByText(/moment everyone has been waiting for/i);
    const scroller = paragraph.closest('[class*="overflow-y-auto"]') as HTMLElement;
    expect(scroller).not.toBeNull();
    expect(scroller.className).toContain("max-h-");
  });

  it("pins the score and hooks rail on desktop beside the adaptation studio", async () => {
    stubClipStudioFetch(makeScoredClip());

    render(<ClipStudioPage />);

    const virality = await screen.findByRole("heading", { name: /virality score/i });
    const rail = virality.closest('[class*="lg:sticky"]') as HTMLElement;
    expect(rail).not.toBeNull();
    expect(rail.className).toContain("lg:top-4");
    expect(rail.className).toContain("lg:self-start");
    expect(rail.className).toContain("lg:row-span-2");

    const studio = await screen.findByRole("heading", { name: /adaptation studio/i });
    const studioWrapper = studio.closest('[class*="lg:col-span-2"]') as HTMLElement;
    expect(studioWrapper).not.toBeNull();
    expect(studioWrapper.parentElement).toBe(rail.parentElement);
    expect(studioWrapper.previousElementSibling).toBe(rail);
  });
});
