const repoApiUrl =
  "https://api.github.com/repos/scowalt/ignite-for-spotify-app";
const cacheKey = "ignite:github-stars";
const cacheTtlMs = 60 * 60 * 1000;
const minStarsToShow = 5;

export function shouldShowStarCount(count: number | undefined): count is number {
  return count !== undefined && count > minStarsToShow;
}
export function formatStarCount(count: number): string {
  if (count < 1000) return String(count);
  const compact = (value: number, suffix: string) => {
    const rounded = Math.floor(value * 10) / 10;
    return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)}${suffix}`;
  };
  return count < 1_000_000
    ? compact(count / 1000, "k")
    : compact(count / 1_000_000, "m");
}

interface CachedStars {
  count: number;
  fetchedAt: number;
}

function readCache(now: number): number | undefined {
  try {
    const raw = localStorage.getItem(cacheKey);
    if (!raw) return undefined;
    const cached = JSON.parse(raw) as CachedStars;
    return now - cached.fetchedAt < cacheTtlMs ? cached.count : undefined;
  } catch {
    return undefined;
  }
}
function writeCache(count: number): void {
  try {
    const cached: CachedStars = { count, fetchedAt: Date.now() };
    localStorage.setItem(cacheKey, JSON.stringify(cached));
  } catch {
    return;
  }
}

export async function fetchStarCount(): Promise<number | undefined> {
  const cached = readCache(Date.now());
  if (cached !== undefined) return cached;

  try {
    const response = await fetch(repoApiUrl, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!response.ok) return undefined;
    const body = (await response.json()) as { stargazers_count?: unknown };
    if (typeof body.stargazers_count !== "number") return undefined;
    writeCache(body.stargazers_count);
    return body.stargazers_count;
  } catch {
    return undefined;
  }
}
