import type { PlaylistSearchCompletion } from "../types/api";

export interface SearchSummaryPresentation {
  heading: string;
  counts: string;
  detail: string;
  isComplete: boolean;
}

export function presentSearchSummary(
  completion: PlaylistSearchCompletion
): SearchSummaryPresentation {
  const counts = `Processed ${completion.processedTracks} of ${completion.totalTracks} playlist tracks; ${completion.matchedTracks} matched, ${completion.skippedTracks} skipped, and ${completion.failedTracks} failed.`;

  if (completion.isComplete) {
    return {
      heading: "Search Complete!",
      counts,
      detail: `Found ${completion.totalMatches} downloadable matches across ${completion.matchedTracks} tracks.`,
      isComplete: true,
    };
  }

  const unprocessed =
    completion.unprocessedTracks === 1
      ? "1 playlist item was not processed."
      : `${completion.unprocessedTracks} playlist items were not processed.`;

  return {
    heading: "Partial Results",
    counts,
    detail: `${completion.failureReason || "The search ended before every playlist item could be processed."} ${unprocessed}`,
    isComplete: false,
  };
}
