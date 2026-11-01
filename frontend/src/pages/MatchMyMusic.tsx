import {
  createSignal,
  createEffect,
  For,
  Show,
  onCleanup,
  untrack,
} from "solid-js";
import { createQuery } from "@tanstack/solid-query";
import { authStore } from "../stores/authStore";
import { spotify, search } from "../lib/api";
import { analytics } from "../lib/analytics";
import { presentSearchSummary } from "../lib/searchSummary";
import {
  formatSavedSearchTime,
  presentSearchFailure,
} from "../lib/savedPlaylistSearch";
import {
  searchHub,
  type SearchProgressUpdate,
  type SearchResultUpdate,
  type SearchCompleteUpdate,
} from "../lib/signalr";
import type {
  PlaylistSearchCompletion,
  PlaylistSearchResult,
  SpotifyPlaylist,
} from "../types/api";
import { AuthSectionSkeleton } from "../components/Skeleton";
import { Drawer } from "../components/Drawer";
import { PlaylistSidebar } from "../components/PlaylistSidebar";

export default function MatchMyMusic() {
  const [selectedPlaylist, setSelectedPlaylist] =
    createSignal<SpotifyPlaylist | null>(null);
  const [isSearching, setIsSearching] = createSignal(false);
  const [isRefreshing, setIsRefreshing] = createSignal(false);
  const [searchProgress, setSearchProgress] = createSignal<{
    processed: number;
    total: number;
    currentItem: string;
  } | null>(null);
  const [searchResults, setSearchResults] =
    createSignal<PlaylistSearchResult[]>([]);
  const [pendingSearchResults, setPendingSearchResults] =
    createSignal<PlaylistSearchResult[]>([]);
  const [searchComplete, setSearchComplete] =
    createSignal<PlaylistSearchCompletion | null>(null);
  const [generatedAt, setGeneratedAt] = createSignal<string | null>(null);
  const [error, setError] = createSignal<string | null>(null);
  const [drawerOpen, setDrawerOpen] = createSignal(false);
  const [expandedResults, setExpandedResults] = createSignal<
    Set<PlaylistSearchResult>
  >(new Set());
  let resultsRef: HTMLDivElement | undefined;
  let activeSearchSessionId: string | null = null;
  let activeSearchHadSavedResults = false;
  let scrollToResultsOnCompletion = false;
  let lastSelectedPlaylistId: string | null = null;
  let shouldApplySavedQuery = true;

  const handleSelectPlaylist = (playlist: SpotifyPlaylist) => {
    if (activeSearchSessionId) {
      searchHub
        .leaveSearchSession(activeSearchSessionId)
        .catch(() => undefined);
      activeSearchSessionId = null;
      setIsSearching(false);
      setIsRefreshing(false);
      setSearchProgress(null);
      shouldApplySavedQuery = true;
    }

    setSelectedPlaylist(playlist);
    analytics.playlistSelected({
      id: playlist.id,
      name: playlist.name,
      trackCount: playlist.totalTracks,
    });
  };

  createEffect(() => {
    if (selectedPlaylist()) {
      setDrawerOpen(false);
    }
  });

  createEffect(() => {
    const playlistId = selectedPlaylist()?.id ?? null;

    if (playlistId === lastSelectedPlaylistId) return;

    lastSelectedPlaylistId = playlistId;
    shouldApplySavedQuery = true;
    setSearchProgress(null);
    setIsRefreshing(false);
    setSearchResults([]);
    setPendingSearchResults([]);
    setSearchComplete(null);
    setGeneratedAt(null);
    setError(null);
    setExpandedResults(new Set<PlaylistSearchResult>());
  });

  createEffect(() => {
    if (
      scrollToResultsOnCompletion &&
      searchComplete() &&
      searchResults().length > 0 &&
      resultsRef
    ) {
      scrollToResultsOnCompletion = false;
      const reduceMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      resultsRef.scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "start",
      });
    }
  });

  const playlistsQuery = createQuery(() => ({
    queryKey: ["playlists"],
    queryFn: () => spotify.getPlaylists(),
    enabled: authStore.isAuthenticated(),
  }));

  const savedResultsQuery = createQuery(() => {
    const playlistId = selectedPlaylist()?.id;

    return {
      queryKey: ["playlist-search", playlistId],
      queryFn: () => search.getSavedPlaylist(playlistId!),
      enabled: authStore.isAuthenticated() && Boolean(playlistId),
      retry: false,
    };
  });

  createEffect(() => {
    const playlistId = selectedPlaylist()?.id;
    const savedSearch = savedResultsQuery.data;

    if (
      !playlistId ||
      isSearching() ||
      !shouldApplySavedQuery ||
      !savedResultsQuery.isSuccess ||
      !savedSearch ||
      savedSearch.playlistId !== playlistId
    ) {
      return;
    }

    setSearchResults(savedSearch.results);
    setPendingSearchResults([]);
    setSearchComplete(savedSearch.completion);
    setGeneratedAt(savedSearch.generatedAt);
    setError(null);
    setExpandedResults(new Set<PlaylistSearchResult>());
  });

  const generateSessionId = () =>
    `search_${Date.now()}_${Math.random().toString(36).substring(7)}`;

  createEffect(() => {
    if (!authStore.isAuthenticated()) return;

    searchHub.start().catch((err) => {
      console.error("Failed to connect to SignalR:", err);
    });

    searchHub.on("ReceiveSearchProgress", (update: SearchProgressUpdate) => {
      if (update.sessionId !== activeSearchSessionId) return;

      setSearchProgress({
        processed: update.processed,
        total: update.total,
        currentItem: update.currentItem,
      });
    });

    searchHub.on("ReceiveSearchResult", (update: SearchResultUpdate) => {
      if (update.sessionId !== activeSearchSessionId) return;

      if (update.matches.length > 0) {
        const result: PlaylistSearchResult = {
          spotifyTrack: update.spotifyTrack,
          matches: update.matches,
        };

        setPendingSearchResults((prev) => [...prev, result]);

        if (!activeSearchHadSavedResults) {
          setSearchResults((prev) => [...prev, result]);
        }
      }
    });

    searchHub.on("ReceiveSearchComplete", (update: SearchCompleteUpdate) => {
      if (update.sessionId !== activeSearchSessionId) return;

      setIsSearching(false);
      setIsRefreshing(false);

      if (update.isComplete) {
        const completedResults = untrack(pendingSearchResults);
        const refreshedPlaylistId = untrack(() => selectedPlaylist()?.id);
        scrollToResultsOnCompletion = completedResults.length > 0;
        setSearchResults(completedResults);
        setSearchComplete(update);
        setGeneratedAt(new Date().toISOString());
        setExpandedResults(new Set<PlaylistSearchResult>());
        savedResultsQuery
          .refetch()
          .then((result) => {
            shouldApplySavedQuery = true;
            const savedSearch = result.data;

            if (
              savedSearch &&
              savedSearch.playlistId === refreshedPlaylistId
            ) {
              setSearchResults(savedSearch.results);
              setSearchComplete(savedSearch.completion);
              setGeneratedAt(savedSearch.generatedAt);
            }
          })
          .catch(() => {
            shouldApplySavedQuery = true;
          });
        analytics.searchCompleted(
          update.totalMatches,
          update.matchedTracks,
          update.totalTracks
        );
      } else {
        if (activeSearchHadSavedResults) {
          shouldApplySavedQuery = true;
          setError(
            presentSearchFailure(
              update.failureReason ||
                "The playlist refresh ended before every track was processed.",
              true,
            ),
          );
        } else {
          const completedResults = untrack(pendingSearchResults);
          scrollToResultsOnCompletion = completedResults.length > 0;
          setSearchResults(completedResults);
          setSearchComplete(update);
        }

        analytics.error(
          "search_partial",
          update.failureReason || "Playlist search returned partial results"
        );
      }

      searchHub.leaveSearchSession(update.sessionId).catch(() => undefined);
      activeSearchSessionId = null;
    });

    searchHub.on("ReceiveError", (update) => {
      if (update.sessionId !== activeSearchSessionId) return;

      setIsSearching(false);
      setIsRefreshing(false);
      shouldApplySavedQuery = true;
      setError(
        presentSearchFailure(update.message, activeSearchHadSavedResults),
      );
      searchHub.leaveSearchSession(update.sessionId).catch(() => undefined);
      activeSearchSessionId = null;
    });

    onCleanup(() => {
      searchHub.stop();
    });
  });

  const startSearch = async () => {
    const playlist = selectedPlaylist();
    if (!playlist) return;

    activeSearchHadSavedResults = generatedAt() !== null;
    setIsRefreshing(activeSearchHadSavedResults);
    shouldApplySavedQuery = false;
    setIsSearching(true);
    setSearchProgress(null);
    setPendingSearchResults([]);
    setError(null);

    if (!activeSearchHadSavedResults) {
      setSearchResults([]);
      setSearchComplete(null);
    }

    setExpandedResults(new Set<PlaylistSearchResult>());

    analytics.searchStarted(playlist.id, playlist.totalTracks);

    const sessionId = generateSessionId();
    activeSearchSessionId = sessionId;

    try {
      await searchHub.start();
      await searchHub.joinSearchSession(sessionId);
      await search.fromPlaylist(playlist.id, sessionId);
    } catch (err) {
      setIsSearching(false);
      setIsRefreshing(false);
      shouldApplySavedQuery = true;
      const message = err instanceof Error ? err.message : "Search failed";
      setError(presentSearchFailure(message, activeSearchHadSavedResults));
      analytics.error("search", message);
      searchHub.leaveSearchSession(sessionId).catch(() => undefined);
      activeSearchSessionId = null;
    }
  };

  const toggleResultVersions = (result: PlaylistSearchResult) => {
    setExpandedResults((current) => {
      const next = new Set(current);

      if (next.has(result)) {
        next.delete(result);
      } else {
        next.add(result);
      }

      return next;
    });
  };

  const searchActionLabel = () => {
    if (savedResultsQuery.isLoading) return "Loading saved results…";
    if (isSearching()) {
      return isRefreshing() ? "Refreshing…" : "Searching…";
    }

    return generatedAt() ? "Refresh Matches" : "Search for Matches";
  };

  const searchProgressLabel = () =>
    isRefreshing() ? "Refreshing matches…" : "Searching…";

  return (
    <Show
      when={!authStore.isLoading() && authStore.isAuthenticated()}
      fallback={
        <div class="space-y-6">
          <div>
            <h1 class="text-2xl font-bold mb-2">Match My Music</h1>
            <p class="text-gray-400">
              Select a Spotify playlist to find matching Rocksmith CDLC (custom
              songs).
            </p>
          </div>

          <Show when={authStore.isLoading()}>
            <AuthSectionSkeleton />
          </Show>

          <Show when={!authStore.isLoading() && !authStore.isAuthenticated()}>
            <div class="bg-gray-800 rounded-lg p-6 text-center">
              <p class="mb-4">Login with Spotify to access your playlists</p>
              <button
                onClick={authStore.login}
                class="bg-spotify-green hover:bg-green-500 text-black font-bold py-2 px-6 rounded-full"
              >
                Login with Spotify
              </button>
            </div>
          </Show>
        </div>
      }
    >
      { }
      <div class="-mx-4 -mt-4 flex">
        { }
        <aside
          class="hidden w-72 flex-col border-r border-gray-700 bg-gray-800 md:flex"
          aria-label="Spotify playlists"
        >
          <PlaylistSidebar
            playlists={playlistsQuery.data}
            isLoading={playlistsQuery.isLoading}
            error={playlistsQuery.error}
            selectedPlaylist={selectedPlaylist()}
            onSelectPlaylist={handleSelectPlaylist}
          />
        </aside>

        { }
        <section
          class="min-w-0 flex-1"
          aria-labelledby="match-my-music-title"
        >
          <div class="p-6 space-y-6">
            { }
            <div class="flex items-center gap-4">
              <Drawer
                isOpen={drawerOpen()}
                onOpenChange={setDrawerOpen}
                title="Your Playlists"
                triggerLabel="Open playlist menu"
                triggerContent={
                  <svg
                    class="h-6 w-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M4 6h16M4 12h16M4 18h16"
                    />
                  </svg>
                }
              >
                <PlaylistSidebar
                  playlists={playlistsQuery.data}
                  isLoading={playlistsQuery.isLoading}
                  error={playlistsQuery.error}
                  selectedPlaylist={selectedPlaylist()}
                  onSelectPlaylist={handleSelectPlaylist}
                />
              </Drawer>
              <div>
                <h1 id="match-my-music-title" class="text-2xl font-bold">
                  Match My Music
                </h1>
                <p class="text-gray-400">
                  Select a playlist to find matching Rocksmith CDLC
                </p>
              </div>
            </div>

            { }
            <Show when={selectedPlaylist()}>
              <div class="sticky top-0 bg-gray-900/95 backdrop-blur-sm z-10 p-4 -mx-6 px-6 border-b border-gray-700">
                <div class="flex items-center gap-4 flex-wrap">
                  <div class="flex min-w-0 items-center gap-3">
                    <Show when={selectedPlaylist()?.imageUrl}>
                      <img
                        src={selectedPlaylist()!.imageUrl!}
                        alt={selectedPlaylist()!.name}
                        class="w-10 h-10 rounded"
                      />
                    </Show>
                    <div class="min-w-0">
                      <p class="truncate font-medium">
                        {selectedPlaylist()?.name}
                      </p>
                      <p class="text-sm text-gray-400">
                        {selectedPlaylist()?.totalTracks} tracks
                      </p>
                      <Show when={generatedAt()}>
                        {(timestamp) => (
                          <p class="mt-0.5 text-xs text-gray-300">
                            Saved {formatSavedSearchTime(timestamp())}
                          </p>
                        )}
                      </Show>
                    </div>
                  </div>
                  <button
                    onClick={startSearch}
                    disabled={isSearching() || savedResultsQuery.isLoading}
                    aria-busy={isSearching()}
                    class="ml-auto shrink-0 rounded-full bg-spotify-green px-6 py-2 font-bold text-black hover:bg-green-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {searchActionLabel()}
                  </button>
                </div>
              </div>
            </Show>

            <Show when={selectedPlaylist() && savedResultsQuery.isLoading}>
              <div
                class="flex items-center gap-3 rounded-lg bg-gray-800 px-4 py-3 text-sm text-gray-300"
                role="status"
                aria-live="polite"
              >
                <svg
                  class="h-4 w-4 animate-spin text-spotify-green"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    class="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  />
                  <path
                    class="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                  />
                </svg>
                Checking for saved results…
              </div>
            </Show>

            <Show
              when={
                selectedPlaylist() &&
                savedResultsQuery.isError &&
                !generatedAt() &&
                !isSearching()
              }
            >
              <div
                class="rounded-lg border border-amber-600 bg-amber-950/60 px-4 py-3 text-sm text-amber-100"
                role="alert"
              >
                Saved results could not be loaded. You can search this playlist
                again.
              </div>
            </Show>

            { }
            <Show when={!selectedPlaylist()}>
              <div class="bg-gray-800 rounded-lg p-8 text-center">
                <svg
                  class="w-12 h-12 mx-auto mb-4 text-gray-500"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
                </svg>
                <p class="text-gray-400">
                  <span class="hidden md:inline">
                    Select a playlist from the sidebar to get started
                  </span>
                  <span class="md:hidden">
                    Tap the menu button above to select a playlist
                  </span>
                </p>
              </div>
            </Show>

            { }
            <Show when={isSearching() && searchProgress()}>
              <div
                class="rounded-lg bg-gray-800 p-4"
                role="status"
                aria-live="polite"
              >
                <div class="flex justify-between mb-2">
                  <span>{searchProgressLabel()}</span>
                  <span>
                    {searchProgress()!.processed} / {searchProgress()!.total}
                  </span>
                </div>
                <div
                  class="h-2 w-full rounded-full bg-gray-700"
                  role="progressbar"
                  aria-label={searchProgressLabel()}
                  aria-valuemin="0"
                  aria-valuemax={searchProgress()!.total}
                  aria-valuenow={searchProgress()!.processed}
                >
                  <div
                    class="bg-spotify-green h-2 rounded-full transition-all"
                    style={{
                      width: `${(searchProgress()!.processed / searchProgress()!.total) * 100}%`,
                    }}
                  />
                </div>
                <p class="text-sm text-gray-400 mt-2">
                  {searchProgress()!.currentItem}
                </p>
                <Show when={isRefreshing()}>
                  <p class="mt-2 text-xs text-gray-300">
                    Your saved results stay available until this refresh
                    completes.
                  </p>
                </Show>
              </div>
            </Show>

            { }
            <Show when={error()}>
              <div
                class="bg-red-900/50 border border-red-500 rounded-lg p-4"
                role="alert"
              >
                <p class="text-red-400">{error()}</p>
              </div>
            </Show>

            { }
            <Show when={searchComplete()}>
              {(completion) => {
                const summary = () => presentSearchSummary(completion());

                return (
                  <div
                    class={`rounded-lg border p-4 ${
                      summary().isComplete
                        ? "bg-green-900/50 border-green-500"
                        : "bg-amber-900/50 border-amber-500"
                    }`}
                    role={summary().isComplete ? "status" : "alert"}
                  >
                    <h3
                      class={`font-semibold mb-2 ${
                        summary().isComplete
                          ? "text-green-400"
                          : "text-amber-300"
                      }`}
                    >
                      {summary().heading}
                    </h3>
                    <p>{summary().counts}</p>
                    <p class="mt-1 text-sm text-gray-300">
                      {summary().detail}
                    </p>
                    <Show when={generatedAt()}>
                      {(timestamp) => (
                        <p class="mt-3 border-t border-current/20 pt-3 text-sm text-gray-300">
                          Showing results generated{" "}
                          <time dateTime={timestamp()}>
                            {formatSavedSearchTime(timestamp())}
                          </time>
                          .
                        </p>
                      )}
                    </Show>
                  </div>
                );
              }}
            </Show>

            { }
            <Show when={searchComplete() && searchResults().length === 0}>
              <div class="bg-gray-800 rounded-lg p-8 text-center">
                <svg
                  class="w-12 h-12 mx-auto mb-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <h3 class="text-lg font-semibold mb-2">No matches found</h3>
                <p class="text-gray-400">
                  Try a different playlist — larger playlists with popular rock
                  and metal songs tend to have more CDLC matches.
                </p>
              </div>
            </Show>

            { }
            <Show when={searchResults().length > 0}>
              <div ref={resultsRef} class="scroll-mt-28 space-y-4">
                <h3 class="text-lg font-semibold">
                  Results ({searchResults().length} tracks with matches)
                </h3>

                <For each={searchResults()}>
                  {(result, index) => {
                    const isExpanded = () => expandedResults().has(result);
                    const visibleMatches = () =>
                      isExpanded() ? result.matches : result.matches.slice(0, 1);
                    const alternateCount = result.matches.length - 1;
                    const versionsId = () =>
                      `match-versions-${result.spotifyTrack.id}-${index()}`;

                    return (
                      <div class="bg-gray-800 rounded-lg p-4">
                        <div class="flex justify-between items-start mb-3">
                          <div>
                            <p class="font-medium">
                              {result.spotifyTrack.name}
                            </p>
                            <p class="text-sm text-gray-400">
                              {result.spotifyTrack.artists.join(", ")} -{" "}
                              {result.spotifyTrack.album}
                            </p>
                            <Show
                              when={result.matches.some(
                                (match) => match.officialDlc,
                              )}
                            >
                              <span
                                class="inline-block mt-1 text-xs bg-rose-600 px-1.5 py-0.5 rounded"
                                title="This track is available as official Rocksmith DLC"
                              >
                                Official DLC
                              </span>
                            </Show>
                          </div>
                          <span class="bg-spotify-green text-black text-sm px-2 py-1 rounded">
                            {result.matches.length} match
                            {result.matches.length !== 1 ? "es" : ""}
                          </span>
                        </div>

                        <div id={versionsId()} class="space-y-2">
                          <For each={visibleMatches()}>
                            {(match) => (
                              <div class="bg-gray-700 rounded p-3 flex justify-between items-center">
                                <div>
                                  <p class="text-sm">
                                    {match.artist} - {match.title}
                                  </p>
                                  <div class="flex gap-2 mt-1">
                                    <Show when={match.officialDlc}>
                                      <span
                                        class="text-xs bg-rose-600 px-1.5 py-0.5 rounded"
                                        title="Official Rocksmith DLC"
                                      >
                                        Official DLC
                                      </span>
                                    </Show>
                                    <Show when={match.lead}>
                                      <span class="text-xs bg-blue-600 px-1.5 py-0.5 rounded">
                                        Lead
                                      </span>
                                    </Show>
                                    <Show when={match.rhythm}>
                                      <span class="text-xs bg-purple-600 px-1.5 py-0.5 rounded">
                                        Rhythm
                                      </span>
                                    </Show>
                                    <Show when={match.bass}>
                                      <span class="text-xs bg-orange-600 px-1.5 py-0.5 rounded">
                                        Bass
                                      </span>
                                    </Show>
                                    <Show when={match.vocals}>
                                      <span class="text-xs bg-pink-600 px-1.5 py-0.5 rounded">
                                        Vocals
                                      </span>
                                    </Show>
                                  </div>
                                </div>
                                <a
                                  href={match.downloadLink}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  class="bg-spotify-green hover:bg-green-500 text-black font-bold text-sm py-1 px-3 rounded shrink-0"
                                  onClick={() =>
                                    analytics.matchDownloaded(
                                      match.id,
                                      match.artist,
                                      match.title,
                                    )
                                  }
                                >
                                  Download
                                </a>
                              </div>
                            )}
                          </For>
                        </div>

                        <Show when={alternateCount > 0}>
                          <button
                            type="button"
                            class="mt-3 text-sm font-medium text-spotify-green hover:text-green-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green focus-visible:ring-offset-2 focus-visible:ring-offset-gray-800 rounded"
                            aria-expanded={isExpanded()}
                            aria-controls={versionsId()}
                            onClick={() => toggleResultVersions(result)}
                          >
                            {isExpanded()
                              ? "Hide alternate versions"
                              : `Show ${alternateCount} more ${alternateCount === 1 ? "version" : "versions"}`}
                          </button>
                        </Show>
                      </div>
                    );
                  }}
                </For>
              </div>
            </Show>
          </div>
        </section>
      </div>
    </Show>
  );
}
