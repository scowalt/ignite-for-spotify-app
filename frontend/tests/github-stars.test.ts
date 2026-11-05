import { describe, expect, test } from "bun:test";
import { formatStarCount, shouldShowStarCount } from "../src/lib/githubStars";

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
  test("reads stargazers_count from the repo's GitHub API response", async () => {
    const { fetchStarCount } = await import("../src/lib/githubStars");
    const originalFetch = globalThis.fetch;
    const requested: string[] = [];
    globalThis.fetch = (async (url: string) => {
      requested.push(url);
      return new Response(JSON.stringify({ stargazers_count: 23_250 }));
    }) as unknown as typeof fetch;
    try {
      expect(await fetchStarCount()).toBe(23_250);
      expect(requested).toEqual([
        "https://api.github.com/repos/scowalt/ignite-for-spotify-app",
      ]);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test("returns undefined when GitHub errors or the body is unexpected", async () => {
    const { fetchStarCount } = await import("../src/lib/githubStars");
    const originalFetch = globalThis.fetch;
    try {
      globalThis.fetch = (async () =>
        new Response("{}", { status: 403 })) as unknown as typeof fetch;
      expect(await fetchStarCount()).toBeUndefined();
      globalThis.fetch = (async () =>
        new Response(JSON.stringify({ stargazers_count: "many" }))) as unknown as typeof fetch;
      expect(await fetchStarCount()).toBeUndefined();
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
