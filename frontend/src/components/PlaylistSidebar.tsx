import { For, Show, createSignal, createMemo, createEffect, on } from "solid-js";
import { createQuery } from "@tanstack/solid-query";
import type { SpotifyPlaylist } from "../types/api";
import { spotify, ApiError } from "../lib/api";
import { parseSpotifyPlaylistId } from "../lib/spotifyUrl";
import { PlaylistSidebarSkeleton } from "./Skeleton";

interface PlaylistSidebarProps {
  playlists: SpotifyPlaylist[] | undefined;
  isLoading: boolean;
  error: Error | null;
  selectedPlaylist: SpotifyPlaylist | null;
  onSelectPlaylist: (playlist: SpotifyPlaylist) => void;
}

export function PlaylistSidebar(props: PlaylistSidebarProps) {
  const [searchQuery, setSearchQuery] = createSignal("");
  const [linkInput, setLinkInput] = createSignal("");
  const [linkParseError, setLinkParseError] = createSignal<string | null>(null);
  const [linkedPlaylistId, setLinkedPlaylistId] = createSignal<string | null>(null);
  const [linkedPlaylist, setLinkedPlaylist] = createSignal<SpotifyPlaylist | null>(null);

  const filteredPlaylists = createMemo(() => {
    const query = searchQuery().toLowerCase().trim();
    if (!query || !props.playlists) return props.playlists;
    return props.playlists.filter((playlist) =>
      playlist.name.toLowerCase().includes(query)
    );
  });

  const linkedPlaylistQuery = createQuery(() => ({
    queryKey: ["spotify-playlist", linkedPlaylistId()],
    queryFn: () => spotify.getPlaylist(linkedPlaylistId()!),
    enabled: linkedPlaylistId() !== null,
    retry: false,
    staleTime: 5 * 60 * 1000,
  }));

  createEffect(
    on(
      () => linkedPlaylistQuery.data,
      (playlist) => {
        if (playlist && playlist.id === linkedPlaylistId()) {
          setLinkedPlaylist(playlist);
          props.onSelectPlaylist(playlist);
        }
      }
    )
  );

  const submitPlaylistLink = () => {
    const input = linkInput();
    if (!input.trim()) return;

    const result = parseSpotifyPlaylistId(input);
    if (!result.ok) {
      setLinkParseError(result.message);
      setLinkedPlaylistId(null);
      setLinkedPlaylist(null);
      return;
    }

    setLinkParseError(null);
    setLinkedPlaylist(null);

    const existing = props.playlists?.find((p) => p.id === result.playlistId);
    if (existing) {
      setLinkedPlaylistId(null);
      props.onSelectPlaylist(existing);
    } else {
      setLinkedPlaylistId(result.playlistId);
    }
  };

  const clearPlaylistLink = () => {
    setLinkInput("");
    setLinkParseError(null);
    setLinkedPlaylistId(null);
    setLinkedPlaylist(null);
  };

  const linkError = createMemo(() => {
    if (linkParseError()) return linkParseError();
    if (!linkedPlaylistQuery.isError) return null;
    const err = linkedPlaylistQuery.error;
    if (err instanceof ApiError && err.details && typeof err.details === "object" && "message" in err.details) {
      const detail = (err.details as { message: unknown }).message;
      if (typeof detail === "string" && detail.trim()) return detail;
    }
    return err.message;
  });

  const renderPlaylistButton = (
    playlist: SpotifyPlaylist,
    opts?: { onClear?: () => void }
  ) => (
    <div
      class={`relative rounded-lg transition-colors ${
        props.selectedPlaylist?.id === playlist.id
          ? "bg-gray-700 border-l-2 border-spotify-green"
          : "hover:bg-gray-700/50"
      }`}
    >
      <button
        onClick={() => props.onSelectPlaylist(playlist)}
        class="w-full flex items-center gap-3 p-2 text-left"
      >
        <Show
          when={playlist.imageUrl}
          fallback={
            <div class="w-10 h-10 bg-gray-700 rounded flex items-center justify-center shrink-0">
              <svg
                class="w-5 h-5 text-gray-500"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
              </svg>
            </div>
          }
        >
          <img
            src={playlist.imageUrl!}
            alt={playlist.name}
            class="w-10 h-10 rounded shrink-0"
          />
        </Show>
        <div class="flex-1 min-w-0">
          <p class="font-medium truncate text-sm">{playlist.name}</p>
          <p class="text-xs text-gray-400">{playlist.totalTracks} tracks</p>
        </div>
      </button>
      <Show when={opts?.onClear}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            opts!.onClear!();
          }}
          class="absolute top-1 right-1 p-1 text-gray-400 hover:text-white rounded"
          aria-label="Clear pasted playlist"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </Show>
    </div>
  );

  return (
    <div class="flex flex-col">
      { }
      <div class="p-2">
        <h3 class="text-sm font-semibold text-gray-400 uppercase tracking-wider px-2 py-2">
          Your Playlists
        </h3>

        { }
        <div class="px-2 pb-2">
          <div class="relative">
            <svg
              class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              placeholder="Filter playlists..."
              value={searchQuery()}
              onInput={(e) => setSearchQuery(e.currentTarget.value)}
              class="w-full bg-gray-700 text-white text-sm rounded-lg pl-9 pr-3 py-2 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-spotify-green"
            />
          </div>
        </div>

        { }
        <div class="px-2 pb-2">
          <div class="relative">
            <svg
              class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"
              />
            </svg>
            <input
              type="text"
              placeholder="Paste a playlist link..."
              value={linkInput()}
              onInput={(e) => {
                setLinkInput(e.currentTarget.value);
                setLinkParseError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  submitPlaylistLink();
                }
              }}
              class="w-full bg-gray-700 text-white text-sm rounded-lg pl-9 pr-3 py-2 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-spotify-green"
            />
          </div>
          <p class="text-xs text-gray-500 mt-1 px-1">
            Match any playlist — not just your own. Press Enter to load it.
          </p>

          <Show when={linkError()}>
            <p class="text-red-400 text-xs mt-1 px-1">{linkError()}</p>
          </Show>

          <Show when={linkedPlaylistQuery.isFetching}>
            <p class="text-gray-400 text-xs mt-1 px-1">Loading playlist…</p>
          </Show>

          <Show when={linkedPlaylist()}>
            <div class="mt-1">
              {renderPlaylistButton(linkedPlaylist()!, { onClear: clearPlaylistLink })}
            </div>
          </Show>
        </div>

        <Show when={props.isLoading}>
          <PlaylistSidebarSkeleton />
        </Show>

        <Show when={props.error}>
          <p class="text-red-500 text-sm px-2">
            Failed to load playlists: {props.error?.message}
          </p>
        </Show>

        <Show when={!props.isLoading && !props.error && props.playlists}>
          <Show when={filteredPlaylists()?.length === 0 && searchQuery()}>
            <p class="text-gray-400 text-sm px-2 py-4 text-center">
              No playlists match "{searchQuery()}"
            </p>
          </Show>
          <div class="space-y-1">
            <For each={filteredPlaylists()}>
              {(playlist) => renderPlaylistButton(playlist)}
            </For>
          </div>
        </Show>
      </div>
    </div>
  );
}
