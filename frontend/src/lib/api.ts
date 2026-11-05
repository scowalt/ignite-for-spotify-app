import type {
  AuthSession,
  DatabaseStats,
  ExportToPlaylistRequest,
  ExportToPlaylistResponse,
  GitHubStars,
  CdlcSearchRequest,
  CdlcSong,
  JobStatus,
  PagedResult,
  PlaylistSearchAccepted,
  SavedPlaylistSearch,
  SpotifyPlaylist,
  SpotifyPlaylistTrackFetchResult,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    let details: unknown;
    const text = await response.text();
    try {
      details = JSON.parse(text);
    } catch {
      details = text;
    }

    const detailMessage =
      typeof details === "string"
        ? details
        : typeof details === "object" &&
            details !== null &&
            "message" in details &&
            typeof details.message === "string"
          ? details.message
          : "";
    const message =
      response.statusText.trim() ||
      detailMessage.trim() ||
      `Request failed with status ${response.status}`;


    throw new ApiError(response.status, message, details);
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  return JSON.parse(text) as T;
}

export const auth = {
  getSession: () => request<AuthSession>("/auth/session"),

  getLoginUrl: () => `${API_BASE}/auth/login`,

  logout: () => request<void>("/auth/logout", { method: "POST" }),

  refresh: () => request<AuthSession>("/auth/refresh", { method: "POST" }),
};

export const spotify = {
  getPlaylists: () => request<SpotifyPlaylist[]>("/spotify/playlists"),

  getPlaylistTracks: (playlistId: string) =>
    request<SpotifyPlaylistTrackFetchResult>(
      `/spotify/playlists/${playlistId}/tracks`
    ),

  getPlaylist: (playlistId: string) =>
    request<SpotifyPlaylist>(`/spotify/playlists/${playlistId}`),
};

export const search = {
  getSavedPlaylist: async (playlistId: string) => {
    try {
      return await request<SavedPlaylistSearch>(
        `/search/from-playlist/${encodeURIComponent(playlistId)}`
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return null;
      }

      throw error;
    }
  },

  fromPlaylist: (playlistId: string, sessionId: string) =>
    request<PlaylistSearchAccepted>("/search/from-playlist", {
      method: "POST",
      body: JSON.stringify({ playlistId, sessionId }),
    }),

  cdlc: (params: CdlcSearchRequest) =>
    request<PagedResult<CdlcSong>>("/search/cdlc", {
      method: "POST",
      body: JSON.stringify(params),
    }),
};

export const exportApi = {
  toPlaylist: (data: ExportToPlaylistRequest) =>
    request<ExportToPlaylistResponse>("/export/to-playlist", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const songs = {
  getStats: () => request<DatabaseStats>("/songs/stats"),
};

export const github = {
  getStars: () => request<GitHubStars>("/github/stars"),
};

export const jobs = {
  getStatus: (jobId: number) => request<JobStatus>(`/jobs/${jobId}/status`),

  getLatest: () => request<JobStatus | null>("/jobs/latest"),

  triggerScrape: () =>
    request<{ jobId: number }>("/jobs/trigger-scrape", { method: "POST" }),

  triggerSpotifyUpdate: () =>
    request<{ jobId: number }>("/jobs/trigger-spotify-update", {
      method: "POST",
    }),
};

export { ApiError };
