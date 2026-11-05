import { github } from "./api";

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

export async function fetchStarCount(): Promise<number | undefined> {
  try {
    const { stars } = await github.getStars();
    return typeof stars === "number" ? stars : undefined;
  } catch {
    return undefined;
  }
}
