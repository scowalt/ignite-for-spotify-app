import { describe, expect, test } from "bun:test";
import { presentSearchSummary } from "../src/lib/searchSummary";
import type { SearchCompleteUpdate } from "../src/lib/signalr";

const complete: SearchCompleteUpdate = {
  sessionId: "search-1",
  totalTracks: 691,
  processedTracks: 689,
  matchedTracks: 117,
  totalMatches: 143,
  skippedTracks: 2,
  failedTracks: 0,
  unprocessedTracks: 0,
  isComplete: true,
  failureReason: null,
  duration: "00:04:12",
};

describe("playlist search summary", () => {
  test("reports a fully accounted large playlist", () => {
    expect(presentSearchSummary(complete)).toEqual({
      heading: "Search Complete!",
      counts:
        "Processed 689 of 691 playlist tracks; 117 matched, 2 skipped, and 0 failed.",
      detail: "Found 143 downloadable matches across 117 tracks.",
      isComplete: true,
    });
  });

  test("labels retained results as partial and includes the reason", () => {
    expect(
      presentSearchSummary({
        ...complete,
        processedTracks: 180,
        matchedTracks: 117,
        skippedTracks: 0,
        unprocessedTracks: 511,
        isComplete: false,
        failureReason: "Spotify stopped returning items at offset 180.",
      })
    ).toEqual({
      heading: "Partial Results",
      counts:
        "Processed 180 of 691 playlist tracks; 117 matched, 0 skipped, and 0 failed.",
      detail:
        "Spotify stopped returning items at offset 180. 511 playlist items were not processed.",
      isComplete: false,
    });
  });
});
