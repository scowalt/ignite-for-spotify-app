import posthog from "posthog-js";
import type { SpotifyUserProfile } from "../types/api";
import { PostHogAnalyticsRuntime } from "./posthogAnalytics";

const runtime = new PostHogAnalyticsRuntime(posthog);

export function initAnalytics() {
  runtime.init(
    import.meta.env.VITE_POSTHOG_KEY,
    import.meta.env.VITE_POSTHOG_HOST,
    import.meta.env.PROD,
  );
}

export const analytics = {
  loginInitiated: () => runtime.capture("login_initiated"),
  loginCompleted: (profile: SpotifyUserProfile) =>
    runtime.loginCompleted(profile),
  logout: () => runtime.logout(),

  playlistSelected: (playlist: {
    id: string;
    name: string;
    trackCount: number;
  }) => runtime.capture("playlist_selected", playlist),
  searchStarted: (playlistId: string, trackCount: number) =>
    runtime.capture("search_started", { playlistId, trackCount }),
  searchCompleted: (matchCount: number, tracksWithMatches: number, totalTracks: number) =>
    runtime.capture("search_completed", { matchCount, tracksWithMatches, totalTracks }),
  matchDownloaded: (songId: number, artist: string, title: string) =>
    runtime.capture("match_downloaded", { songId, artist, title }),

  cdlcSearchSubmitted: (filters: Record<string, unknown>) =>
    runtime.capture("cdlc_search_submitted", filters),
  songsSelected: (count: number) =>
    runtime.capture("songs_selected", { count }),
  exportStarted: (songCount: number, playlistName: string) =>
    runtime.capture("export_started", { songCount, playlistName }),
  exportCompleted: (songCount: number, playlistName: string, tracksAdded: number) =>
    runtime.capture("export_completed", { songCount, playlistName, tracksAdded }),

  error: (type: string, message: string) =>
    runtime.capture("error", { type, message }),
};
