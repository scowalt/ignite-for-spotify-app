namespace Ignite.Core.Entities

open System
open System.ComponentModel.DataAnnotations.Schema

type ScrapingJobType =
    | CdlcFull = 0
    | CdlcIncremental = 1
    | IgnitionFull = 2
    | IgnitionIncremental = 3

type ScrapingJobStatus =
    | Pending = 0
    | Running = 1
    | Completed = 2
    | Failed = 3
    | Cancelled = 4

[<AllowNullLiteral>]
type ScrapingJob() =
    member val Id = 0 with get, set
    member val JobType = ScrapingJobType.CdlcFull with get, set
    member val Status = ScrapingJobStatus.Pending with get, set
    member val HangfireJobId: string | null = null with get, set
    member val StartedAt: Nullable<DateTime> = Nullable() with get, set
    member val CompletedAt: Nullable<DateTime> = Nullable() with get, set
    member val SongsProcessed = 0 with get, set
    member val SongsAdded = 0 with get, set
    member val SongsUpdated = 0 with get, set
    member val ErrorMessage: string | null = null with get, set
    member val CreatedAt = DateTime.UtcNow with get, set

[<AllowNullLiteral>]
type Song() =
    member val Id = 0 with get, set
    member val Artist = "" with get, set
    member val Title = "" with get, set
    member val Album = "" with get, set
    member val Tuning: string | null = null with get, set
    member val Version: string | null = null with get, set
    member val Author: string | null = null with get, set

    [<Column("date_added_to_ignition")>]
    member val DateAddedToCdlc: Nullable<DateTime> = Nullable() with get, set

    [<Column("date_updated_in_ignition")>]
    member val DateUpdatedInCdlc: Nullable<DateTime> = Nullable() with get, set

    member val Lead = false with get, set
    member val Rhythm = false with get, set
    member val Bass = false with get, set
    member val Vocals = false with get, set
    member val DynamicDifficulty = false with get, set
    member val OfficialDlc = false with get, set
    member val DownloadLink = "" with get, set
    member val SpotifyTrackId: string | null = null with get, set
    member val CreatedAt = DateTime.UtcNow with get, set
    member val UpdatedAt = DateTime.UtcNow with get, set

[<AllowNullLiteral>]
type UserSession() =
    member val Id = "" with get, set
    member val SpotifyUserId: string | null = null with get, set
    member val SpotifyAccessToken: string | null = null with get, set
    member val SpotifyRefreshToken: string | null = null with get, set
    member val TokenExpiresAt: Nullable<DateTime> = Nullable() with get, set
    member val CreatedAt = DateTime.UtcNow with get, set
    member val UpdatedAt = DateTime.UtcNow with get, set

[<AllowNullLiteral>]
type PlaylistSearchSnapshot() =
    member val Id = 0 with get, set
    member val SpotifyUserId = "" with get, set
    member val PlaylistId = "" with get, set
    member val ResultsJson = "[]" with get, set
    member val TotalTracks = 0 with get, set
    member val ProcessedTracks = 0 with get, set
    member val MatchedTracks = 0 with get, set
    member val TotalMatches = 0 with get, set
    member val SkippedTracks = 0 with get, set
    member val FailedTracks = 0 with get, set
    member val UnprocessedTracks = 0 with get, set
    member val DurationTicks = 0L with get, set
    member val GeneratedAt = DateTime.UtcNow with get, set
    member val CreatedAt = DateTime.UtcNow with get, set
    member val UpdatedAt = DateTime.UtcNow with get, set

[<RequireQualifiedAccess>]
module UserSessionId =
    [<Literal>]
    let Prefix = "session_"

    let create () = Prefix + Guid.NewGuid().ToString("N")

    let canonicalize (id: string) =
        match Guid.TryParse(id) with
        | true, guid -> guid.ToString("N")
        | false, _ -> id
