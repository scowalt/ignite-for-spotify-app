import { afterEach, describe, expect, mock, test } from "bun:test";
import { search } from "../src/lib/api";
import {
  formatSavedSearchTime,
  presentSearchFailure,
} from "../src/lib/savedPlaylistSearch";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("saved playlist searches", () => {
  test("loads the latest saved snapshot for an encoded playlist ID", async () => {
    const snapshot = {
      playlistId: "playlist/with slash",
      generatedAt: "2030-01-02T03:04:05.000Z",
      results: [],
      completion: {
        totalTracks: 12,
        processedTracks: 12,
        matchedTracks: 0,
        totalMatches: 0,
        skippedTracks: 0,
        failedTracks: 0,
        unprocessedTracks: 0,
        isComplete: true,
        failureReason: null,
        duration: "00:00:01",
      },
    };
    const fetchMock = mock(async () => Response.json(snapshot));
    globalThis.fetch = fetchMock as typeof fetch;

    await expect(
      search.getSavedPlaylist("playlist/with slash")
    ).resolves.toEqual(snapshot);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/search/from-playlist/playlist%2Fwith%20slash",
      {
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      }
    );
  });

  test("treats a missing snapshot as a normal empty cache", async () => {
    globalThis.fetch = mock(
      async () => new Response(null, { status: 404, statusText: "Not Found" })
    ) as typeof fetch;

    await expect(search.getSavedPlaylist("new-playlist")).resolves.toBeNull();
  });

  test("surfaces cache failures that are not missing snapshots", async () => {
    globalThis.fetch = mock(
      async () =>
        Response.json(
          { message: "Snapshot store unavailable" },
          { status: 503, statusText: "Service Unavailable" }
        )
    ) as typeof fetch;

    await expect(search.getSavedPlaylist("playlist")).rejects.toMatchObject({
      status: 503,
      message: "Service Unavailable",
    });
  });

  test("keeps refresh failures explicit about preserved results", () => {
    expect(presentSearchFailure("Refresh failed.", true)).toBe(
      "Refresh failed. Your previous saved results are still shown."
    );
    expect(presentSearchFailure("Search failed.", false)).toBe(
      "Search failed."
    );
  });

  test("formats valid freshness timestamps and handles invalid data", () => {
    expect(formatSavedSearchTime("2030-01-02T03:04:05.000Z")).toContain(
      "2030"
    );
    expect(formatSavedSearchTime("not-a-date")).toBe("time unavailable");
  });
});
