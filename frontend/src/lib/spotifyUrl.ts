
export type PlaylistIdParseResult =
  | { ok: true; playlistId: string }
  | { ok: false; message: string };

const PLAYLIST_ID_PATTERN = /^[A-Za-z0-9]{22}$/;

const SPOTIFY_ENTITY_NAMES: Record<string, string> = {
  track: "track",
  album: "album",
  artist: "artist",
  episode: "episode",
  show: "podcast show",
  user: "user profile",
};

export function parseSpotifyPlaylistId(input: string): PlaylistIdParseResult {
  const trimmed = input.trim();

  if (!trimmed) {
    return { ok: false, message: "Paste a Spotify playlist link." };
  }

  const uriMatch = /^spotify:([a-z]+):([A-Za-z0-9]+)(?:[?].*)?$/i.exec(trimmed);
  if (uriMatch) {
    const [, entityType, id] = uriMatch;
    if (entityType.toLowerCase() !== "playlist") {
      return notAPlaylist(entityType.toLowerCase());
    }
    return withId(id);
  }

  if (/^https?:\/\//i.test(trimmed) || /^open\.spotify\.com/i.test(trimmed)) {
    let url: URL;
    try {
      url = new URL(/^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`);
    } catch {
      return { ok: false, message: "That doesn't look like a valid link." };
    }

    if (!/(^|\.)spotify\.com$/i.test(url.hostname)) {
      return {
        ok: false,
        message: "That's not a Spotify link. Copy the playlist link from Spotify.",
      };
    }

    const segments = url.pathname.split("/").filter(Boolean);
    const entityIndex = segments.findIndex((s) => !/^intl-[a-z-]+$/i.test(s));

    if (entityIndex === -1 || entityIndex >= segments.length - 1) {
      return {
        ok: false,
        message: "That link doesn't point to a playlist. Copy the link via Share → Copy link to playlist.",
      };
    }

    const entityType = segments[entityIndex].toLowerCase();
    const id = segments[entityIndex + 1];

    if (entityType !== "playlist") {
      return notAPlaylist(entityType);
    }

    return withId(id);
  }

  if (PLAYLIST_ID_PATTERN.test(trimmed)) {
    return { ok: true, playlistId: trimmed };
  }

  return {
    ok: false,
    message:
      "Couldn't find a playlist ID. Paste a Spotify playlist link (Share → Copy link to playlist).",
  };
}

function withId(id: string): PlaylistIdParseResult {
  if (!PLAYLIST_ID_PATTERN.test(id)) {
    return {
      ok: false,
      message: "That link doesn't contain a valid playlist ID.",
    };
  }
  return { ok: true, playlistId: id };
}

function notAPlaylist(entityType: string): PlaylistIdParseResult {
  const name = SPOTIFY_ENTITY_NAMES[entityType] ?? entityType;
  return {
    ok: false,
    message: `That link is a ${name}, not a playlist. In Spotify, use Share → Copy link to playlist.`,
  };
}
