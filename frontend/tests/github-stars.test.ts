import { afterEach, describe, expect, test } from "bun:test";
import {
  fetchStarCount,
  formatStarCount,
  shouldShowStarCount,
} from "../src/lib/githubStars";

describe("formatStarCount", () => {
  test("leaves counts under a thousand as-is", () => {
    expect(formatStarCount(0)).toBe("0");
    expect(formatStarCount(999)).toBe("999");
  });

  test("abbreviates thousands with one truncated decimal", () => {
    expect(formatStarCount(1000)).toBe("1k");
    expect(formatStarCount(1250)).toBe("1.2k");
    expect(formatStarCount(23_250)).toBe("23.2k");
  });

  test("abbreviates millions", () => {
    expect(formatStarCount(1_500_000)).toBe("1.5m");
  });
});

describe("shouldShowStarCount", () => {
  test("hides the count until there are more than 5 stars", () => {
    expect(shouldShowStarCount(undefined)).toBe(false);
    expect(shouldShowStarCount(0)).toBe(false);
    expect(shouldShowStarCount(5)).toBe(false);
    expect(shouldShowStarCount(6)).toBe(true);
  });
});

describe("fetchStarCount", () => {
  const originalFetch = globalThis.fetch;

  function respondWith(response: Response) {
    const requested: string[] = [];
    globalThis.fetch = (async (url: string) => {
      requested.push(url);
      return response;
    }) as unknown as typeof fetch;
    return requested;
  }

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("reads the star count from the app's own API, not GitHub", async () => {
    const requested = respondWith(
      new Response(JSON.stringify({ stars: 23_250 })),
    );

    expect(await fetchStarCount()).toBe(23_250);
    expect(requested).toEqual(["/api/github/stars"]);
  });

  test("returns undefined when the backend has no count yet", async () => {
    respondWith(new Response(JSON.stringify({ stars: null })));

    expect(await fetchStarCount()).toBeUndefined();
  });

  test("returns undefined when the request fails", async () => {
    respondWith(new Response("{}", { status: 500 }));

    expect(await fetchStarCount()).toBeUndefined();
  });
});
