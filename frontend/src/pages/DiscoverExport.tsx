import { createSignal, createMemo, For, Show } from "solid-js";
import { createQuery, createMutation } from "@tanstack/solid-query";
import { authStore } from "../stores/authStore";
import { search, exportApi, songs } from "../lib/api";
import { analytics } from "../lib/analytics";
import type { CdlcSong, CdlcSearchRequest } from "../types/api";
import { StatsSkeleton, SearchResultsTableSkeleton } from "../components/Skeleton";

export default function DiscoverExport() {
  const [artist, setArtist] = createSignal("");
  const [title, setTitle] = createSignal("");
  const [album, setAlbum] = createSignal("");
  const [lead, setLead] = createSignal(false);
  const [rhythm, setRhythm] = createSignal(false);
  const [bass, setBass] = createSignal(false);
  const [vocals, setVocals] = createSignal(false);
  const [hasSpotifyId, setHasSpotifyId] = createSignal(true);
  const [page, setPage] = createSignal(1);

  const [selectedSongs, setSelectedSongs] = createSignal<Set<number>>(
    new Set()
  );

  const [playlistName, setPlaylistName] = createSignal("");
  const [playlistDescription, setPlaylistDescription] = createSignal("");
  const [isPublic, setIsPublic] = createSignal(false);

  const searchParams = createMemo<CdlcSearchRequest>(() => ({
    artist: artist() || undefined,
    title: title() || undefined,
    album: album() || undefined,
    lead: lead() || undefined,
    rhythm: rhythm() || undefined,
    bass: bass() || undefined,
    vocals: vocals() || undefined,
    hasSpotifyId: hasSpotifyId() || undefined,
    page: page(),
    pageSize: 50,
  }));

  const searchQuery = createQuery(() => ({
    queryKey: ["cdlc-search", searchParams()],
    queryFn: () => search.cdlc(searchParams()),
    enabled:
      !!(artist() || title() || album() || lead() || rhythm() || bass() || vocals()),
  }));

  const statsQuery = createQuery(() => ({
    queryKey: ["db-stats"],
    queryFn: () => songs.getStats(),
  }));

  const exportMutation = createMutation(() => ({
    mutationFn: () =>
      exportApi.toPlaylist({
        songIds: Array.from(selectedSongs()),
        playlistName: playlistName(),
        description: playlistDescription() || undefined,
        isPublic: isPublic(),
      }),
    onSuccess: (data) => {
      analytics.exportCompleted(selectedSongs().size, data.playlist.name, data.tracksAdded);
      setSelectedSongs(new Set<number>());
      setPlaylistName("");
      setPlaylistDescription("");
    },
    onError: (error) => {
      analytics.error("export", error instanceof Error ? error.message : "Export failed");
    },
  }));

  const toggleSong = (id: number) => {
    setSelectedSongs((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    if (searchQuery.data?.items) {
      const count = searchQuery.data.items.length;
      setSelectedSongs(new Set(searchQuery.data.items.map((s) => s.id)));
      analytics.songsSelected(count);
    }
  };

  const clearSelection = () => {
    setSelectedSongs(new Set<number>());
    analytics.songsSelected(0);
  };

  const handleSearch = (e: Event) => {
    e.preventDefault();
    setPage(1);
    analytics.cdlcSearchSubmitted({
      artist: artist() || undefined,
      title: title() || undefined,
      album: album() || undefined,
      lead: lead() || undefined,
      rhythm: rhythm() || undefined,
      bass: bass() || undefined,
      vocals: vocals() || undefined,
      hasSpotifyId: hasSpotifyId() || undefined,
    });
  };

  const handleExport = async (e: Event) => {
    e.preventDefault();
    if (selectedSongs().size === 0 || !playlistName()) return;
    analytics.exportStarted(selectedSongs().size, playlistName());
    exportMutation.mutate();
  };

  return (
    <div class="page">
      <div>
        <h1 class="page-intro-title">Discover & Export</h1>
        <p class="page-intro-text">
          Search the CDLC database and export matching songs to a Spotify
          playlist.
        </p>
      </div>

      { }
      <Show when={statsQuery.isLoading}>
        <StatsSkeleton />
      </Show>
      <Show when={statsQuery.data}>
        <div class="panel discover-stats">
          <div>
            <p class="discover-stat-label">Total Songs</p>
            <p class="discover-stat-value">
              {statsQuery.data!.totalSongs.toLocaleString()}
            </p>
          </div>
          <div>
            <p class="discover-stat-label">With Spotify Match</p>
            <p class="discover-stat-value">
              {statsQuery.data!.songsWithSpotifyId.toLocaleString()}
            </p>
          </div>
          <div>
            <p class="discover-stat-label">Match Rate</p>
            <p class="discover-stat-value">
              {statsQuery.data!.percentageWithSpotify.toFixed(1)}%
            </p>
          </div>
        </div>
      </Show>

      { }
      <form onSubmit={handleSearch} class="panel discover-form stack-section">
        <h3 class="section-title discover-form-title">Search Filters</h3>

        <div class="discover-filter-fields">
          <div>
            <label class="field-label">Artist</label>
            <input
              type="text"
              value={artist()}
              onInput={(e) => setArtist(e.currentTarget.value)}
              class="text-input"
              placeholder="e.g., Metallica"
            />
          </div>
          <div>
            <label class="field-label">Title</label>
            <input
              type="text"
              value={title()}
              onInput={(e) => setTitle(e.currentTarget.value)}
              class="text-input"
              placeholder="e.g., Enter Sandman"
            />
          </div>
          <div>
            <label class="field-label">Album</label>
            <input
              type="text"
              value={album()}
              onInput={(e) => setAlbum(e.currentTarget.value)}
              class="text-input"
              placeholder="e.g., Black Album"
            />
          </div>
        </div>

        <div class="discover-part-filters">
          <label class="checkbox-label">
            <input
              type="checkbox"
              checked={lead()}
              onChange={(e) => setLead(e.currentTarget.checked)}
              class="checkbox"
            />
            <span>Lead</span>
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              checked={rhythm()}
              onChange={(e) => setRhythm(e.currentTarget.checked)}
              class="checkbox"
            />
            <span>Rhythm</span>
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              checked={bass()}
              onChange={(e) => setBass(e.currentTarget.checked)}
              class="checkbox"
            />
            <span>Bass</span>
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              checked={vocals()}
              onChange={(e) => setVocals(e.currentTarget.checked)}
              class="checkbox"
            />
            <span>Vocals</span>
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              checked={hasSpotifyId()}
              onChange={(e) => setHasSpotifyId(e.currentTarget.checked)}
              class="checkbox"
            />
            <span>Has Spotify Match</span>
          </label>
        </div>

        <button
          type="submit"
          class="button-primary"
        >
          Search
        </button>
      </form>

      { }
      <Show when={searchQuery.isLoading}>
        <SearchResultsTableSkeleton />
      </Show>

      <Show when={searchQuery.isError}>
        <div class="alert alert-error">
          <p class="alert-error-text">{searchQuery.error?.message}</p>
        </div>
      </Show>

      <Show when={searchQuery.data && searchQuery.data.items.length > 0}>
        <div class="stack-section">
          <div class="results-header">
            <h3 class="section-title">
              Results ({searchQuery.data!.totalCount.toLocaleString()} songs)
            </h3>
            <div class="results-actions">
              <button
                onClick={selectAll}
                class="results-select-all"
              >
                Select All
              </button>
              <span class="results-divider">|</span>
              <button
                onClick={clearSelection}
                class="results-clear"
              >
                Clear ({selectedSongs().size})
              </button>
            </div>
          </div>

          { }
          <div class="panel results-table-wrap">
            <table class="results-table">
              <thead>
                <tr>
                  <th class="results-select-column" />
                  <th class="results-heading">Artist</th>
                  <th class="results-heading">Title</th>
                  <th class="results-heading">Album</th>
                  <th class="results-heading">Parts</th>
                  <th class="results-heading">Spotify</th>
                </tr>
              </thead>
              <tbody>
                <For each={searchQuery.data!.items}>
                  {(song: CdlcSong) => (
                    <tr
                      class={
                        selectedSongs().has(song.id)
                          ? "results-row results-row-selected"
                          : "results-row"
                      }
                      onClick={() => toggleSong(song.id)}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedSongs().has(song.id)}
                          onChange={() => toggleSong(song.id)}
                          onClick={(e) => e.stopPropagation()}
                          class="checkbox"
                        />
                      </td>
                      <td>{song.artist}</td>
                      <td>{song.title}</td>
                      <td class="results-album">{song.album}</td>
                      <td>
                        <div class="badge-list">
                          <Show when={song.officialDlc}>
                            <span
                              class="badge badge-official"
                              title="Official Rocksmith DLC"
                            >
                              Official
                            </span>
                          </Show>
                          <Show when={song.lead}>
                            <span class="badge badge-lead">
                              L
                            </span>
                          </Show>
                          <Show when={song.rhythm}>
                            <span class="badge badge-rhythm">
                              R
                            </span>
                          </Show>
                          <Show when={song.bass}>
                            <span class="badge badge-bass">
                              B
                            </span>
                          </Show>
                          <Show when={song.vocals}>
                            <span class="badge badge-vocals">
                              V
                            </span>
                          </Show>
                        </div>
                      </td>
                      <td>
                        <Show
                          when={song.spotifyTrackId}
                          fallback={
                            <span class="results-no-match">None</span>
                          }
                        >
                          <span class="results-match">✓</span>
                        </Show>
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>

          { }
          <Show when={searchQuery.data!.hasMore}>
            <div class="pagination">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page() === 1}
                class="pagination-button"
              >
                Previous
              </button>
              <span class="pagination-status">
                Page {searchQuery.data!.page} of{" "}
                {Math.ceil(
                  searchQuery.data!.totalCount / searchQuery.data!.pageSize
                )}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!searchQuery.data!.hasMore}
                class="pagination-button"
              >
                Next
              </button>
            </div>
          </Show>
        </div>
      </Show>

      <Show when={searchQuery.data && searchQuery.data.items.length === 0}>
        <div class="discover-empty">
          No songs found matching your criteria.
        </div>
      </Show>

      { }
      <Show when={selectedSongs().size > 0 && authStore.isAuthenticated()}>
        <form
          onSubmit={handleExport}
          class="panel discover-form stack-section"
        >
          <h3 class="section-title">
            Export {selectedSongs().size} Songs to Spotify
          </h3>

          <div class="discover-export-fields">
            <div>
              <label class="field-label">
                Playlist Name *
              </label>
              <input
                type="text"
                value={playlistName()}
                onInput={(e) => setPlaylistName(e.currentTarget.value)}
                class="text-input"
                placeholder="My Rocksmith Playlist"
                required
              />
            </div>
            <div>
              <label class="field-label">Description</label>
              <input
                type="text"
                value={playlistDescription()}
                onInput={(e) => setPlaylistDescription(e.currentTarget.value)}
                class="text-input"
                placeholder="Songs from Rocksmith CDLC"
              />
            </div>
          </div>

          <label class="checkbox-label">
            <input
              type="checkbox"
              checked={isPublic()}
              onChange={(e) => setIsPublic(e.currentTarget.checked)}
              class="checkbox"
            />
            <span>Make playlist public</span>
          </label>

          <button
            type="submit"
            disabled={exportMutation.isPending || !playlistName()}
            class="button-primary"
          >
            {exportMutation.isPending ? "Creating..." : "Create Spotify Playlist"}
          </button>
        </form>
      </Show>

      <Show when={selectedSongs().size > 0 && !authStore.isAuthenticated()}>
        <div class="panel login-prompt">
          <p class="login-prompt-text">Login with Spotify to export your selection</p>
          <button
            onClick={authStore.login}
            class="button-primary"
          >
            Login with Spotify
          </button>
        </div>
      </Show>

      { }
      <Show when={exportMutation.isSuccess}>
        <div class="alert alert-success">
          <h3 class="alert-title">Playlist Created!</h3>
          <p>
            Added {exportMutation.data!.tracksAdded} tracks to "
            {exportMutation.data!.playlist.name}"
            {exportMutation.data!.tracksSkipped > 0 && (
              <span class="discover-export-skipped">
                {" "}
                ({exportMutation.data!.tracksSkipped} skipped - no Spotify match)
              </span>
            )}
          </p>
        </div>
      </Show>

      { }
      <Show when={exportMutation.isError}>
        <div class="alert alert-error">
          <p class="alert-error-text">{exportMutation.error?.message}</p>
        </div>
      </Show>
    </div>
  );
}
