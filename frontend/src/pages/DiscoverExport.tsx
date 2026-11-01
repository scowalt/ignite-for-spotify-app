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
    <div class="space-y-6">
      <div>
        <h1 class="text-2xl font-bold mb-2">Discover & Export</h1>
        <p class="text-gray-400">
          Search the CDLC database and export matching songs to a Spotify
          playlist.
        </p>
      </div>

      { }
      <Show when={statsQuery.isLoading}>
        <StatsSkeleton />
      </Show>
      <Show when={statsQuery.data}>
        <div class="bg-gray-800 rounded-lg p-4 flex gap-8">
          <div>
            <p class="text-sm text-gray-400">Total Songs</p>
            <p class="text-2xl font-bold">
              {statsQuery.data!.totalSongs.toLocaleString()}
            </p>
          </div>
          <div>
            <p class="text-sm text-gray-400">With Spotify Match</p>
            <p class="text-2xl font-bold">
              {statsQuery.data!.songsWithSpotifyId.toLocaleString()}
            </p>
          </div>
          <div>
            <p class="text-sm text-gray-400">Match Rate</p>
            <p class="text-2xl font-bold">
              {statsQuery.data!.percentageWithSpotify.toFixed(1)}%
            </p>
          </div>
        </div>
      </Show>

      { }
      <form onSubmit={handleSearch} class="bg-gray-800 rounded-lg p-6 space-y-4">
        <h3 class="text-lg font-semibold mb-4">Search Filters</h3>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">Artist</label>
            <input
              type="text"
              value={artist()}
              onInput={(e) => setArtist(e.currentTarget.value)}
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-spotify-green focus:outline-none"
              placeholder="e.g., Metallica"
            />
          </div>
          <div>
            <label class="block text-sm text-gray-400 mb-1">Title</label>
            <input
              type="text"
              value={title()}
              onInput={(e) => setTitle(e.currentTarget.value)}
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-spotify-green focus:outline-none"
              placeholder="e.g., Enter Sandman"
            />
          </div>
          <div>
            <label class="block text-sm text-gray-400 mb-1">Album</label>
            <input
              type="text"
              value={album()}
              onInput={(e) => setAlbum(e.currentTarget.value)}
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-spotify-green focus:outline-none"
              placeholder="e.g., Black Album"
            />
          </div>
        </div>

        <div class="flex flex-wrap gap-4">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={lead()}
              onChange={(e) => setLead(e.currentTarget.checked)}
              class="rounded border-gray-600 bg-gray-700 text-spotify-green focus:ring-spotify-green"
            />
            <span>Lead</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={rhythm()}
              onChange={(e) => setRhythm(e.currentTarget.checked)}
              class="rounded border-gray-600 bg-gray-700 text-spotify-green focus:ring-spotify-green"
            />
            <span>Rhythm</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={bass()}
              onChange={(e) => setBass(e.currentTarget.checked)}
              class="rounded border-gray-600 bg-gray-700 text-spotify-green focus:ring-spotify-green"
            />
            <span>Bass</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={vocals()}
              onChange={(e) => setVocals(e.currentTarget.checked)}
              class="rounded border-gray-600 bg-gray-700 text-spotify-green focus:ring-spotify-green"
            />
            <span>Vocals</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={hasSpotifyId()}
              onChange={(e) => setHasSpotifyId(e.currentTarget.checked)}
              class="rounded border-gray-600 bg-gray-700 text-spotify-green focus:ring-spotify-green"
            />
            <span>Has Spotify Match</span>
          </label>
        </div>

        <button
          type="submit"
          class="bg-spotify-green hover:bg-green-500 text-black font-bold py-2 px-6 rounded-full"
        >
          Search
        </button>
      </form>

      { }
      <Show when={searchQuery.isLoading}>
        <SearchResultsTableSkeleton />
      </Show>

      <Show when={searchQuery.isError}>
        <div class="bg-red-900/50 border border-red-500 rounded-lg p-4">
          <p class="text-red-400">{searchQuery.error?.message}</p>
        </div>
      </Show>

      <Show when={searchQuery.data && searchQuery.data.items.length > 0}>
        <div class="space-y-4">
          <div class="flex justify-between items-center">
            <h3 class="text-lg font-semibold">
              Results ({searchQuery.data!.totalCount.toLocaleString()} songs)
            </h3>
            <div class="flex gap-2">
              <button
                onClick={selectAll}
                class="text-sm text-spotify-green hover:underline"
              >
                Select All
              </button>
              <span class="text-gray-600">|</span>
              <button
                onClick={clearSelection}
                class="text-sm text-gray-400 hover:text-white"
              >
                Clear ({selectedSongs().size})
              </button>
            </div>
          </div>

          { }
          <div class="bg-gray-800 rounded-lg overflow-hidden">
            <table class="w-full">
              <thead class="bg-gray-700">
                <tr>
                  <th class="w-8 px-4 py-2" />
                  <th class="text-left px-4 py-2">Artist</th>
                  <th class="text-left px-4 py-2">Title</th>
                  <th class="text-left px-4 py-2">Album</th>
                  <th class="text-left px-4 py-2">Parts</th>
                  <th class="text-left px-4 py-2">Spotify</th>
                </tr>
              </thead>
              <tbody>
                <For each={searchQuery.data!.items}>
                  {(song: CdlcSong) => (
                    <tr
                      class={`border-t border-gray-700 hover:bg-gray-700/50 cursor-pointer ${
                        selectedSongs().has(song.id) ? "bg-gray-700/50" : ""
                      }`}
                      onClick={() => toggleSong(song.id)}
                    >
                      <td class="px-4 py-2">
                        <input
                          type="checkbox"
                          checked={selectedSongs().has(song.id)}
                          onChange={() => toggleSong(song.id)}
                          onClick={(e) => e.stopPropagation()}
                          class="rounded border-gray-600 bg-gray-700 text-spotify-green focus:ring-spotify-green"
                        />
                      </td>
                      <td class="px-4 py-2">{song.artist}</td>
                      <td class="px-4 py-2">{song.title}</td>
                      <td class="px-4 py-2 text-gray-400">{song.album}</td>
                      <td class="px-4 py-2">
                        <div class="flex gap-1">
                          <Show when={song.officialDlc}>
                            <span
                              class="text-xs bg-rose-600 px-1.5 py-0.5 rounded"
                              title="Official Rocksmith DLC"
                            >
                              Official
                            </span>
                          </Show>
                          <Show when={song.lead}>
                            <span class="text-xs bg-blue-600 px-1.5 py-0.5 rounded">
                              L
                            </span>
                          </Show>
                          <Show when={song.rhythm}>
                            <span class="text-xs bg-purple-600 px-1.5 py-0.5 rounded">
                              R
                            </span>
                          </Show>
                          <Show when={song.bass}>
                            <span class="text-xs bg-orange-600 px-1.5 py-0.5 rounded">
                              B
                            </span>
                          </Show>
                          <Show when={song.vocals}>
                            <span class="text-xs bg-pink-600 px-1.5 py-0.5 rounded">
                              V
                            </span>
                          </Show>
                        </div>
                      </td>
                      <td class="px-4 py-2">
                        <Show
                          when={song.spotifyTrackId}
                          fallback={
                            <span class="text-gray-500 text-sm">None</span>
                          }
                        >
                          <span class="text-spotify-green text-sm">✓</span>
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
            <div class="flex justify-center gap-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page() === 1}
                class="px-4 py-2 bg-gray-700 rounded disabled:opacity-50"
              >
                Previous
              </button>
              <span class="px-4 py-2">
                Page {searchQuery.data!.page} of{" "}
                {Math.ceil(
                  searchQuery.data!.totalCount / searchQuery.data!.pageSize
                )}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!searchQuery.data!.hasMore}
                class="px-4 py-2 bg-gray-700 rounded disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </Show>
        </div>
      </Show>

      <Show when={searchQuery.data && searchQuery.data.items.length === 0}>
        <div class="text-gray-400 text-center py-8">
          No songs found matching your criteria.
        </div>
      </Show>

      { }
      <Show when={selectedSongs().size > 0 && authStore.isAuthenticated()}>
        <form
          onSubmit={handleExport}
          class="bg-gray-800 rounded-lg p-6 space-y-4"
        >
          <h3 class="text-lg font-semibold">
            Export {selectedSongs().size} Songs to Spotify
          </h3>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-gray-400 mb-1">
                Playlist Name *
              </label>
              <input
                type="text"
                value={playlistName()}
                onInput={(e) => setPlaylistName(e.currentTarget.value)}
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-spotify-green focus:outline-none"
                placeholder="My Rocksmith Playlist"
                required
              />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Description</label>
              <input
                type="text"
                value={playlistDescription()}
                onInput={(e) => setPlaylistDescription(e.currentTarget.value)}
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 focus:border-spotify-green focus:outline-none"
                placeholder="Songs from Rocksmith CDLC"
              />
            </div>
          </div>

          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isPublic()}
              onChange={(e) => setIsPublic(e.currentTarget.checked)}
              class="rounded border-gray-600 bg-gray-700 text-spotify-green focus:ring-spotify-green"
            />
            <span>Make playlist public</span>
          </label>

          <button
            type="submit"
            disabled={exportMutation.isPending || !playlistName()}
            class="bg-spotify-green hover:bg-green-500 disabled:opacity-50 text-black font-bold py-2 px-6 rounded-full"
          >
            {exportMutation.isPending ? "Creating..." : "Create Spotify Playlist"}
          </button>
        </form>
      </Show>

      <Show when={selectedSongs().size > 0 && !authStore.isAuthenticated()}>
        <div class="bg-gray-800 rounded-lg p-6 text-center">
          <p class="mb-4">Login with Spotify to export your selection</p>
          <button
            onClick={authStore.login}
            class="bg-spotify-green hover:bg-green-500 text-black font-bold py-2 px-6 rounded-full"
          >
            Login with Spotify
          </button>
        </div>
      </Show>

      { }
      <Show when={exportMutation.isSuccess}>
        <div class="bg-green-900/50 border border-green-500 rounded-lg p-4">
          <h3 class="font-semibold text-green-400 mb-2">Playlist Created!</h3>
          <p>
            Added {exportMutation.data!.tracksAdded} tracks to "
            {exportMutation.data!.playlist.name}"
            {exportMutation.data!.tracksSkipped > 0 && (
              <span class="text-gray-400">
                {" "}
                ({exportMutation.data!.tracksSkipped} skipped - no Spotify match)
              </span>
            )}
          </p>
        </div>
      </Show>

      { }
      <Show when={exportMutation.isError}>
        <div class="bg-red-900/50 border border-red-500 rounded-lg p-4">
          <p class="text-red-400">{exportMutation.error?.message}</p>
        </div>
      </Show>
    </div>
  );
}
