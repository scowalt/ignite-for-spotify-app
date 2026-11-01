export interface SpotifyPlaylist {
  id: string;
  name: string;
  description: string | null;
  totalTracks: number;
  imageUrl: string | null;
}

export interface SpotifyTrack {
  id: string;
  name: string;
  artists: string[];
  album: string;
  durationMs: number;
}

export interface SpotifyPlaylistTrack {
  track: SpotifyTrack;
  addedAt: string;
}

export interface SpotifyPlaylistTrackFetchResult {
  totalItems: number;
  retrievedItems: number;
  tracks: SpotifyPlaylistTrack[];
  skippedItems: number;
  unretrievedItems: number;
  isComplete: boolean;
  failureReason: string | null;
}

export interface SpotifyUserProfile {
  id: string;
  displayName: string;
  imageUrl: string | null;
}

export interface CdlcSong {
  id: number;
  artist: string;
  title: string;
  album: string;
  author: string | null;
  version: string | null;
  tuning: string | null;
  lead: boolean;
  rhythm: boolean;
  bass: boolean;
  vocals: boolean;
  officialDlc: boolean;
  dynamicDifficulty: boolean;
  downloadLink: string;
  spotifyTrackId: string | null;
  hasSpotifyMatch?: boolean;
}

export interface PagedResult<T> {
  items: T[];
  totalCount: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export interface CdlcSearchRequest {
  artist?: string;
  title?: string;
  album?: string;
  author?: string;
  lead?: boolean;
  rhythm?: boolean;
  bass?: boolean;
  vocals?: boolean;
  dynamicDifficulty?: boolean;
  hasSpotifyId?: boolean;
  page?: number;
  pageSize?: number;
}

export interface PlaylistSearchResult {
  spotifyTrack: {
    id: string;
    name: string;
    artists: string[];
    album: string;
  };
  matches: PlaylistCdlcMatch[];
}

export interface PlaylistCdlcMatch {
  id: number;
  artist: string;
  title: string;
  album: string;
  author: string | null;
  lead: boolean;
  rhythm: boolean;
  bass: boolean;
  vocals: boolean;
  officialDlc: boolean;
  downloadLink: string;
}

export interface PlaylistSearchCompletion {
  totalTracks: number;
  processedTracks: number;
  matchedTracks: number;
  totalMatches: number;
  skippedTracks: number;
  failedTracks: number;
  unprocessedTracks: number;
  isComplete: boolean;
  failureReason: string | null;
  duration: string;
}

export interface SavedPlaylistSearch {
  playlistId: string;
  generatedAt: string;
  results: PlaylistSearchResult[];
  completion: PlaylistSearchCompletion;
}

export interface PlaylistSearchAccepted {
  jobId: string;
  playlistId: string;
  sessionId: string;
}

export interface ExportToPlaylistRequest {
  songIds: number[];
  playlistName: string;
  description?: string;
  isPublic?: boolean;
}

export interface ExportToPlaylistResponse {
  playlist: {
    id: string;
    name: string;
    description: string | null;
    totalTracks: number;
    imageUrl: string | null;
  };
  tracksAdded: number;
  tracksSkipped: number;
}

export interface AuthSession {
  sessionId: string;
  profile: SpotifyUserProfile;
  expiresAt: string;
}

export interface DatabaseStats {
  totalSongs: number;
  songsWithSpotifyId: number;
  percentageWithSpotify: number;
}

export interface JobStatus {
  id: number;
  status: string;
  jobType: string;
  startedAt: string | null;
  completedAt: string | null;
  songsProcessed: number;
  songsAdded: number;
  songsUpdated: number;
  errorMessage: string | null;
}
