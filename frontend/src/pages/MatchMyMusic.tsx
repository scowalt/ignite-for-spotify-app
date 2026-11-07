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
        <div class="page">
          <div>
            <h1 class="page-intro-title">Match My Music</h1>
            <p class="page-intro-text">
              Select a Spotify playlist to find matching Rocksmith CDLC (custom
              songs).
            </p>
          </div>

          <Show when={authStore.isLoading()}>
            <AuthSectionSkeleton />
          </Show>

          <Show when={!authStore.isLoading() && !authStore.isAuthenticated()}>
            <div class="panel login-prompt">
              <p class="login-prompt-text">Login with Spotify to access your playlists</p>
              <button
                onClick={authStore.login}
                class="button-primary"
              >
                Login with Spotify
              </button>
            </div>
          </Show>
        </div>
      }
    >
      { }
      <div class="match-layout">
        { }
        <aside
          class="match-sidebar"
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
          class="match-main"
          aria-labelledby="match-my-music-title"
        >
          <div class="match-content">
            { }
            <div class="match-header">
              <Drawer
                isOpen={drawerOpen()}
                onOpenChange={setDrawerOpen}
                title="Your Playlists"
                triggerLabel="Open playlist menu"
                triggerContent={
                  <svg
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
                <h1 id="match-my-music-title" class="match-title">
                  Match My Music
                </h1>
                <p class="page-intro-text">
                  Select a playlist to find matching Rocksmith CDLC
                </p>
              </div>
            </div>

            { }
            <Show when={selectedPlaylist()}>
              <div class="match-toolbar">
                <div class="match-toolbar-inner">
                  <div class="match-playlist">
                    <Show when={selectedPlaylist()?.imageUrl}>
                      <img
                        src={selectedPlaylist()!.imageUrl!}
                        alt={selectedPlaylist()!.name}
                        class="match-playlist-image"
                      />
                    </Show>
                    <div class="match-playlist-info">
                      <p class="match-playlist-name">
                        {selectedPlaylist()?.name}
                      </p>
                      <p class="match-playlist-tracks">
                        {selectedPlaylist()?.totalTracks} tracks
                      </p>
                      <Show when={generatedAt()}>
                        {(timestamp) => (
                          <p class="match-playlist-saved">
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
                    class="button-primary match-search-button focus-ring"
                  >
                    {searchActionLabel()}
                  </button>
                </div>
              </div>
            </Show>

            <Show when={selectedPlaylist() && savedResultsQuery.isLoading}>
              <div
                class="panel match-status"
                role="status"
                aria-live="polite"
              >
                <svg
                  class="spinner"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    class="spinner-track"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  />
                  <path
                    class="spinner-head"
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
                class="match-saved-error"
                role="alert"
              >
                Saved results could not be loaded. You can search this playlist
                again.
              </div>
            </Show>

            { }
            <Show when={!selectedPlaylist()}>
              <div class="panel empty-state">
                <svg
                  class="empty-state-icon"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
                </svg>
                <p class="empty-state-text">
                  <span class="match-hint-desktop">
                    Select a playlist from the sidebar to get started
                  </span>
                  <span class="match-hint-mobile">
                    Tap the menu button above to select a playlist
                  </span>
                </p>
              </div>
            </Show>

            { }
            <Show when={isSearching() && searchProgress()}>
              <div
                class="panel match-progress"
                role="status"
                aria-live="polite"
              >
                <div class="match-progress-header">
                  <span>{searchProgressLabel()}</span>
                  <span>
                    {searchProgress()!.processed} / {searchProgress()!.total}
                  </span>
                </div>
                <div
                  class="progress-track"
                  role="progressbar"
                  aria-label={searchProgressLabel()}
                  aria-valuemin="0"
                  aria-valuemax={searchProgress()!.total}
                  aria-valuenow={searchProgress()!.processed}
                >
                  <div
                    class="progress-fill"
                    style={{
                      width: `${(searchProgress()!.processed / searchProgress()!.total) * 100}%`,
                    }}
                  />
                </div>
                <p class="match-progress-item">
                  {searchProgress()!.currentItem}
                </p>
                <Show when={isRefreshing()}>
                  <p class="match-progress-note">
                    Your saved results stay available until this refresh
                    completes.
                  </p>
                </Show>
              </div>
            </Show>

            { }
            <Show when={error()}>
              <div
                class="alert alert-error"
                role="alert"
              >
                <p class="alert-error-text">{error()}</p>
              </div>
            </Show>

            { }
            <Show when={searchComplete()}>
              {(completion) => {
                const summary = () => presentSearchSummary(completion());

                return (
                  <div
                    class={
                      summary().isComplete
                        ? "alert alert-success"
                        : "alert alert-warning"
                    }
                    role={summary().isComplete ? "status" : "alert"}
                  >
                    <h3 class="alert-title">
                      {summary().heading}
                    </h3>
                    <p>{summary().counts}</p>
                    <p class="match-summary-detail">
                      {summary().detail}
                    </p>
                    <Show when={generatedAt()}>
                      {(timestamp) => (
                        <p class="match-summary-generated">
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
              <div class="panel empty-state">
                <svg
                  class="empty-state-icon"
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
                <h3 class="empty-state-title">No matches found</h3>
                <p class="empty-state-text">
                  Try a different playlist — larger playlists with popular rock
                  and metal songs tend to have more CDLC matches.
                </p>
              </div>
            </Show>

            { }
            <Show when={searchResults().length > 0}>
              <div ref={resultsRef} class="match-results stack-section">
                <h3 class="section-title">
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
                      <div class="panel match-result">
                        <div class="match-result-header">
                          <div>
                            <p class="match-track-name">
                              {result.spotifyTrack.name}
                            </p>
                            <p class="match-track-meta">
                              {result.spotifyTrack.artists.join(", ")} -{" "}
                              {result.spotifyTrack.album}
                            </p>
                            <Show
                              when={result.matches.some(
                                (match) => match.officialDlc,
                              )}
                            >
                              <span
                                class="badge badge-official match-track-official"
                                title="This track is available as official Rocksmith DLC"
                              >
                                Official DLC
                              </span>
                            </Show>
                          </div>
                          <span class="match-count">
                            {result.matches.length} match
                            {result.matches.length !== 1 ? "es" : ""}
                          </span>
                        </div>

                        <div id={versionsId()} class="match-versions">
                          <For each={visibleMatches()}>
                            {(match) => (
                              <div class="match-version">
                                <div>
                                  <p class="match-version-title">
                                    {match.artist} - {match.title}
                                  </p>
                                  <div class="match-version-badges">
                                    <Show when={match.officialDlc}>
                                      <span
                                        class="badge badge-official"
                                        title="Official Rocksmith DLC"
                                      >
                                        Official DLC
                                      </span>
                                    </Show>
                                    <Show when={match.lead}>
                                      <span class="badge badge-lead">
                                        Lead
                                      </span>
                                    </Show>
                                    <Show when={match.rhythm}>
                                      <span class="badge badge-rhythm">
                                        Rhythm
                                      </span>
                                    </Show>
                                    <Show when={match.bass}>
                                      <span class="badge badge-bass">
                                        Bass
                                      </span>
                                    </Show>
                                    <Show when={match.vocals}>
                                      <span class="badge badge-vocals">
                                        Vocals
                                      </span>
                                    </Show>
                                  </div>
                                </div>
                                <a
                                  href={match.downloadLink}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  class="button-download"
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
                            class="match-versions-toggle focus-ring"
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
