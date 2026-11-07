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
      class={
        props.selectedPlaylist?.id === playlist.id
          ? "playlist-item playlist-item-selected"
          : "playlist-item playlist-item-selectable"
      }
    >
      <button
        onClick={() => props.onSelectPlaylist(playlist)}
        class="playlist-item-button"
      >
        <Show
          when={playlist.imageUrl}
          fallback={
            <div class="playlist-art-fallback">
              <svg
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
            class="playlist-art"
          />
        </Show>
        <div class="playlist-item-text">
          <p class="playlist-item-name">{playlist.name}</p>
          <p class="playlist-item-count">{playlist.totalTracks} tracks</p>
        </div>
      </button>
      <Show when={opts?.onClear}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            opts!.onClear!();
          }}
          class="playlist-item-clear"
          aria-label="Clear pasted playlist"
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </Show>
    </div>
  );

  return (
    <div class="playlist-sidebar">
      { }
      <div class="playlist-sidebar-inner">
        <h3 class="playlist-sidebar-title">
          Your Playlists
        </h3>

        { }
        <div class="playlist-sidebar-field">
          <div class="playlist-search">
            <svg
              class="playlist-search-icon"
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
              class="playlist-search-input"
            />
          </div>
        </div>

        { }
        <div class="playlist-sidebar-field">
          <div class="playlist-search">
            <svg
              class="playlist-search-icon"
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
              class="playlist-search-input"
            />
          </div>
          <p class="playlist-link-hint">
            Match any playlist — not just your own. Press Enter to load it.
          </p>

          <Show when={linkError()}>
            <p class="playlist-link-error">{linkError()}</p>
          </Show>

          <Show when={linkedPlaylistQuery.isFetching}>
            <p class="playlist-link-status">Loading playlist…</p>
          </Show>

          <Show when={linkedPlaylist()}>
            <div class="playlist-linked">
              {renderPlaylistButton(linkedPlaylist()!, { onClear: clearPlaylistLink })}
            </div>
          </Show>
        </div>

        <Show when={props.isLoading}>
          <PlaylistSidebarSkeleton />
        </Show>

        <Show when={props.error}>
          <p class="playlist-load-error">
            Failed to load playlists: {props.error?.message}
          </p>
        </Show>

        <Show when={!props.isLoading && !props.error && props.playlists}>
          <Show when={filteredPlaylists()?.length === 0 && searchQuery()}>
            <p class="playlist-empty">
              No playlists match "{searchQuery()}"
            </p>
          </Show>
          <div class="playlist-list">
            <For each={filteredPlaylists()}>
              {(playlist) => renderPlaylistButton(playlist)}
            </For>
          </div>
        </Show>
      </div>
    </div>
  );
}
