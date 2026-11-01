namespace Ignite.Core.Interfaces

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities


[<AllowNullLiteral>]
type SpotifyTrack(id: string, name: string, artists: string array, album: string, durationMs: int) =
    member _.Id = id
    member _.Name = name
    member _.Artists = artists
    member _.Album = album
    member _.DurationMs = durationMs

    override this.Equals(obj) =
        match obj with
        | :? SpotifyTrack as other ->
            this.Id = other.Id
            && this.Name = other.Name
            && this.Artists = other.Artists
            && this.Album = other.Album
            && this.DurationMs = other.DurationMs
        | _ -> false

    override this.GetHashCode() =
        HashCode.Combine(this.Id, this.Name, this.Album, this.DurationMs)

[<AllowNullLiteral>]
type SpotifyPlaylist(id: string, name: string, description: string | null, totalTracks: int, imageUrl: string | null) =
    member _.Id = id
    member _.Name = name
    member _.Description = description
    member _.TotalTracks = totalTracks
    member _.ImageUrl = imageUrl

type SpotifyPlaylistTrack(track: SpotifyTrack, addedAt: DateTime) =
    member _.Track = track
    member _.AddedAt = addedAt

[<AllowNullLiteral>]
type SpotifyPlaylistTrackFetchResult
    (
        totalItems: int,
        retrievedItems: int,
        tracks: IReadOnlyList<SpotifyPlaylistTrack>,
        skippedItems: int,
        isComplete: bool,
        failureReason: string | null
    ) =
    member _.TotalItems = totalItems
    member _.RetrievedItems = retrievedItems
    member _.Tracks = tracks
    member _.SkippedItems = skippedItems
    member _.IsComplete = isComplete
    member _.FailureReason = failureReason
    member _.UnretrievedItems = max 0 (totalItems - retrievedItems)

type SpotifyTokens(accessToken: string, refreshToken: string, expiresAt: DateTime) =
    member _.AccessToken = accessToken
    member _.RefreshToken = refreshToken
    member _.ExpiresAt = expiresAt

[<AllowNullLiteral>]
type SpotifyUserProfile(id: string, displayName: string, imageUrl: string | null) =
    member _.Id = id
    member _.DisplayName = displayName
    member _.ImageUrl = imageUrl


[<AllowNullLiteral>]
type MatchResult(song: Song, spotifyMatch: SpotifyTrack | null, matchStrategy: string | null) =
    member _.Song = song
    member _.SpotifyMatch = spotifyMatch
    member _.MatchStrategy = matchStrategy


[<AllowNullLiteral>]
type SongSearchFilter() =
    member val Artist: string | null = null with get, set
    member val Title: string | null = null with get, set
    member val Album: string | null = null with get, set
    member val Author: string | null = null with get, set
    member val Lead: Nullable<bool> = Nullable() with get, set
    member val Rhythm: Nullable<bool> = Nullable() with get, set
    member val Bass: Nullable<bool> = Nullable() with get, set
    member val Vocals: Nullable<bool> = Nullable() with get, set
    member val DynamicDifficulty: Nullable<bool> = Nullable() with get, set
    member val HasSpotifyId: Nullable<bool> = Nullable() with get, set

type PagedResult<'T>(items: IReadOnlyList<'T>, totalCount: int, page: int, pageSize: int) =
    member _.Items = items
    member _.TotalCount = totalCount
    member _.Page = page
    member _.PageSize = pageSize
    member _.HasMore = page * pageSize < totalCount


type ISpotifyClientService =
    abstract GetUserPlaylistsAsync:
        accessToken: string * cancellationToken: CancellationToken -> Task<IReadOnlyList<SpotifyPlaylist>>

    abstract GetPlaylistAsync:
        accessToken: string * playlistId: string * cancellationToken: CancellationToken ->
            Task<SpotifyPlaylist>

    abstract GetPlaylistTracksAsync:
        accessToken: string * playlistId: string * cancellationToken: CancellationToken ->
            Task<SpotifyPlaylistTrackFetchResult>

    abstract SearchTrackAsync:
        accessToken: string * query: string * cancellationToken: CancellationToken -> Task<SpotifyTrack>

    abstract CreatePlaylistAsync:
        accessToken: string *
        name: string *
        description: string | null *
        isPublic: bool *
        cancellationToken: CancellationToken ->
            Task<SpotifyPlaylist>

    abstract AddTracksToPlaylistAsync:
        accessToken: string *
        playlistId: string *
        trackIds: IEnumerable<string> *
        cancellationToken: CancellationToken ->
            Task

type ISpotifyAuthService =
    abstract GetAuthorizationUrl: state: string -> string
    abstract ExchangeCodeAsync: code: string * cancellationToken: CancellationToken -> Task<SpotifyTokens>
    abstract RefreshTokenAsync: refreshToken: string * cancellationToken: CancellationToken -> Task<SpotifyTokens>

    abstract GetUserProfileAsync:
        accessToken: string * cancellationToken: CancellationToken -> Task<SpotifyUserProfile>

type ISongMatchingService =
    abstract FindSpotifyMatchAsync:
        accessToken: string *
        artist: string *
        title: string *
        album: string | null *
        cancellationToken: CancellationToken ->
            Task<SpotifyTrack>

    abstract MatchSongsToSpotifyAsync:
        accessToken: string *
        songs: IEnumerable<Song> *
        progress: IProgress<int> | null *
        cancellationToken: CancellationToken ->
            Task<IReadOnlyList<MatchResult>>

type ISongRepository =
    abstract GetByIdAsync: id: int * cancellationToken: CancellationToken -> Task<Song>

    abstract FindByUniqueKeyAsync:
        artist: string *
        title: string *
        author: string | null *
        version: string | null *
        cancellationToken: CancellationToken ->
            Task<Song>

    abstract SearchAsync:
        filter: SongSearchFilter * page: int * pageSize: int * cancellationToken: CancellationToken ->
            Task<PagedResult<Song>>

    abstract GetBySpotifyTrackIdsAsync:
        spotifyTrackIds: IEnumerable<string> * cancellationToken: CancellationToken -> Task<IReadOnlyList<Song>>

    abstract GetSongsWithoutSpotifyIdAsync: limit: int * cancellationToken: CancellationToken -> Task<IReadOnlyList<Song>>
    abstract CreateAsync: song: Song * cancellationToken: CancellationToken -> Task<Song>
    abstract UpdateAsync: song: Song * cancellationToken: CancellationToken -> Task<Song>
    abstract UpsertAsync: song: Song * cancellationToken: CancellationToken -> Task<int>

    abstract BulkUpsertAsync:
        songs: IEnumerable<Song> * cancellationToken: CancellationToken -> Task<struct (int * int)>

    abstract GetStatsAsync: cancellationToken: CancellationToken -> Task<struct (int * int)>

    abstract FullTextSearchAsync:
        query: string * limit: int * cancellationToken: CancellationToken -> Task<IReadOnlyList<Song>>

type IScrapingJobRepository =
    abstract GetByIdAsync: id: int * cancellationToken: CancellationToken -> Task<ScrapingJob>

    abstract GetLatestAsync:
        jobType: Nullable<ScrapingJobType> * cancellationToken: CancellationToken -> Task<ScrapingJob>

    abstract CreateAsync: job: ScrapingJob * cancellationToken: CancellationToken -> Task<ScrapingJob>
    abstract UpdateAsync: job: ScrapingJob * cancellationToken: CancellationToken -> Task<ScrapingJob>

type ICdlcScraper =
    abstract ScrapeAllSongsAsync:
        progress: IProgress<struct (int * int)> | null * cancellationToken: CancellationToken ->
            IAsyncEnumerable<Song>

    abstract GetTotalSongCountAsync: cancellationToken: CancellationToken -> Task<int>

type IUserSessionRepository =
    abstract GetByIdAsync: id: string * cancellationToken: CancellationToken -> Task<UserSession>
    abstract CreateAsync: session: UserSession * cancellationToken: CancellationToken -> Task<UserSession>
    abstract UpdateAsync: session: UserSession * cancellationToken: CancellationToken -> Task<UserSession>
    abstract DeleteAsync: id: string * cancellationToken: CancellationToken -> Task
    abstract DeleteExpiredAsync: cancellationToken: CancellationToken -> Task

type IPlaylistSearchSnapshotRepository =
    abstract GetLatestAsync:
        spotifyUserId: string * playlistId: string * cancellationToken: CancellationToken ->
            Task<PlaylistSearchSnapshot>

    abstract UpsertAsync:
        snapshot: PlaylistSearchSnapshot * cancellationToken: CancellationToken ->
            Task<PlaylistSearchSnapshot>

    abstract DeleteBySpotifyUserIdAsync:
        spotifyUserId: string * cancellationToken: CancellationToken -> Task
