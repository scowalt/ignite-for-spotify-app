namespace Ignite.Api

#nowarn "3261"

open System
open System.Linq
open System.Linq.Expressions
open System.Text.Json
open System.Threading
open System.Threading.Tasks
open Hangfire
open Hangfire.Server
open Ignite.Api.Hubs
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Microsoft.AspNetCore.Http
open Microsoft.Extensions.Logging
open SpotifyAPI.Web

type PlaylistSearchSessionException(message: string) =
    inherit Exception(message)

type PlaylistFetchException(message: string) =
    inherit Exception(message)

type PlaylistSearchJob
    (
        spotifyClient: ISpotifyClientService,
        songRepository: ISongRepository,
        authService: ISpotifyAuthService,
        sessionRepository: IUserSessionRepository,
        snapshotRepository: IPlaylistSearchSnapshotRepository,
        notifications: IHubNotificationService,
        logger: ILogger<PlaylistSearchJob>
    ) =

    let getValidSessionAsync (sessionId: string) (cancellationToken: CancellationToken) =
        task {
            let! session = sessionRepository.GetByIdAsync(sessionId, cancellationToken)

            if isNull session || String.IsNullOrEmpty(session.SpotifyAccessToken) then
                return null
            elif session.TokenExpiresAt.HasValue && session.TokenExpiresAt.Value <= DateTime.UtcNow then
                if String.IsNullOrEmpty(session.SpotifyRefreshToken) then
                    return null
                else
                    let! tokens = authService.RefreshTokenAsync(session.SpotifyRefreshToken, cancellationToken)
                    session.SpotifyAccessToken <- tokens.AccessToken
                    session.SpotifyRefreshToken <- tokens.RefreshToken
                    session.TokenExpiresAt <- tokens.ExpiresAt
                    do! sessionRepository.UpdateAsync(session, cancellationToken) :> Task
                    return session
            else
                return session
        }

    [<AutomaticRetry(Attempts = 0)>]
    [<Queue("matching")>]
    member _.ExecuteAsync
        (
            igniteSessionId: string,
            playlistId: string,
            signalRSessionId: string,
            context: PerformContext | null,
            cancellationToken: CancellationToken
        ) =
        task {
            let jobId =
                if not (isNull context) && not (isNull context.BackgroundJob) then
                    context.BackgroundJob.Id
                else
                    Guid.NewGuid().ToString()

            let startTime = DateTime.UtcNow
            logger.LogInformation("Starting playlist search job {JobId} for playlist {PlaylistId}", jobId, playlistId)

            try
                let! session = getValidSessionAsync igniteSessionId cancellationToken

                if isNull session then
                    raise (
                        PlaylistSearchSessionException(
                            "Your Spotify session expired before the search could start. Sign in again and retry."
                        )
                    )

                let! fetchResult =
                    try
                        spotifyClient.GetPlaylistTracksAsync(
                            session.SpotifyAccessToken,
                            playlistId,
                            cancellationToken
                        )
                    with
                    | :? APIException as ex when
                        ex.Response <> null
                        && ex.Response.StatusCode = Net.HttpStatusCode.NotFound
                        ->
                        raise (
                            PlaylistFetchException(
                                "This playlist is private or does not exist. Check the link and try again."
                            )
                        )
                    | :? APIException as ex when
                        ex.Response <> null
                        && ex.Response.StatusCode = Net.HttpStatusCode.Forbidden
                        ->
                        raise (PlaylistFetchException("You do not have access to this playlist."))

                let mutable processedTracks = 0
                let mutable matchedTracks = 0
                let mutable totalMatches = 0
                let mutable failedTracks = 0
                let searchResults = ResizeArray<PlaylistSearchResult>()

                for playlistTrack in fetchResult.Tracks do
                    cancellationToken.ThrowIfCancellationRequested()
                    let track = playlistTrack.Track
                    let artist = String.Join(", ", track.Artists)
                    processedTracks <- processedTracks + 1

                    do!
                        notifications.SendSearchProgressAsync(
                            signalRSessionId,
                            processedTracks,
                            fetchResult.Tracks.Count,
                            $"{artist} - {track.Name}"
                        )

                    try
                        let filter = SongSearchFilter(Artist = artist, Title = track.Name)
                        let! matches = songRepository.SearchAsync(filter, 1, 10, cancellationToken)

                        let matchList =
                            matches.Items
                            |> Seq.map (fun song ->
                                CdlcMatchInfo(
                                    song.Id,
                                    song.Artist,
                                    song.Title,
                                    (if isNull song.Album then "" else song.Album),
                                    song.Author,
                                    song.Lead,
                                    song.Rhythm,
                                    song.Bass,
                                    song.Vocals,
                                    song.OfficialDlc,
                                    (if isNull song.DownloadLink then "" else song.DownloadLink)
                                ))
                            |> Seq.toList

                        if matchList.Length > 0 then
                            matchedTracks <- matchedTracks + 1
                            totalMatches <- totalMatches + matchList.Length

                            let trackInfo =
                                SpotifyTrackInfo(
                                    track.Id,
                                    track.Name,
                                    track.Artists.ToArray(),
                                    track.Album
                                )

                            searchResults.Add(PlaylistSearchResult(trackInfo, matchList))

                            do!
                                notifications.SendSearchResultAsync(
                                    signalRSessionId,
                                    trackInfo,
                                    matchList
                                )
                    with
                    | :? OperationCanceledException ->
                        raise (OperationCanceledException(cancellationToken))
                    | ex ->
                        failedTracks <- failedTracks + 1
                        logger.LogWarning(
                            ex,
                            "Playlist search job {JobId} could not match track {TrackId}",
                            jobId,
                            track.Id
                        )

                let unprocessedTracks =
                    max 0 (fetchResult.TotalItems - processedTracks - fetchResult.SkippedItems)

                let isComplete =
                    fetchResult.IsComplete
                    && failedTracks = 0
                    && unprocessedTracks = 0

                let failureReason =
                    if isComplete then
                        null
                    elif not (String.IsNullOrWhiteSpace(fetchResult.FailureReason)) then
                        fetchResult.FailureReason
                    elif failedTracks > 0 then
                        $"{failedTracks} track search attempt(s) failed. Partial results are shown."
                    else
                        $"{unprocessedTracks} playlist item(s) could not be processed. Partial results are shown."

                let duration = DateTime.UtcNow - startTime

                if isComplete then
                    let spotifyUserId =
                        if String.IsNullOrWhiteSpace(session.SpotifyUserId) then
                            session.Id
                        else
                            session.SpotifyUserId

                    let serializationOptions =
                        JsonSerializerOptions(PropertyNamingPolicy = JsonNamingPolicy.CamelCase)

                    let snapshot =
                        PlaylistSearchSnapshot(
                            SpotifyUserId = spotifyUserId,
                            PlaylistId = playlistId,
                            ResultsJson = JsonSerializer.Serialize(searchResults, serializationOptions),
                            TotalTracks = fetchResult.TotalItems,
                            ProcessedTracks = processedTracks,
                            MatchedTracks = matchedTracks,
                            TotalMatches = totalMatches,
                            SkippedTracks = fetchResult.SkippedItems,
                            FailedTracks = failedTracks,
                            UnprocessedTracks = unprocessedTracks,
                            DurationTicks = duration.Ticks,
                            GeneratedAt = DateTime.UtcNow
                        )

                    do! snapshotRepository.UpsertAsync(snapshot, cancellationToken) :> Task

                do!
                    notifications.SendSearchCompleteAsync(
                        signalRSessionId,
                        fetchResult.TotalItems,
                        processedTracks,
                        matchedTracks,
                        totalMatches,
                        fetchResult.SkippedItems,
                        failedTracks,
                        unprocessedTracks,
                        isComplete,
                        failureReason,
                        duration
                    )

                logger.LogInformation(
                    "Playlist search job {JobId} finished: {Processed}/{Total} processed, {Matched} matched, {Skipped} skipped, {Failed} failed, complete={IsComplete}",
                    jobId,
                    processedTracks,
                    fetchResult.TotalItems,
                    matchedTracks,
                    fetchResult.SkippedItems,
                    failedTracks,
                    isComplete
                )
            with
            | :? OperationCanceledException as ex ->
                logger.LogWarning(ex, "Playlist search job {JobId} was cancelled", jobId)
                do! notifications.SendErrorAsync(signalRSessionId, "The playlist search was cancelled before it completed.")
                return raise ex
            | :? PlaylistSearchSessionException as ex ->
                logger.LogWarning(ex, "Playlist search job {JobId} could not use its stored session", jobId)
                do! notifications.SendErrorAsync(signalRSessionId, ex.Message)
                return ()
            | :? PlaylistFetchException as ex ->
                logger.LogWarning(ex, "Playlist search job {JobId} could not fetch playlist {PlaylistId}", jobId, playlistId)
                do! notifications.SendErrorAsync(signalRSessionId, ex.Message)
                return raise ex
            | ex ->
                logger.LogError(ex, "Playlist search job {JobId} failed", jobId)
                do! notifications.SendErrorAsync(signalRSessionId, "The playlist search failed before it completed. Try again.")
                return raise ex
        }
        :> Task

module PlaylistSearchQueue =
    let enqueue
        (jobClient: IBackgroundJobClient)
        (igniteSessionId: string)
        (playlistId: string)
        (signalRSessionId: string)
        =
        let parameter = Expression.Parameter(typeof<PlaylistSearchJob>, "job")
        let methodInfo = typeof<PlaylistSearchJob>.GetMethod("ExecuteAsync")

        let call =
            Expression.Call(
                parameter,
                methodInfo,
                Expression.Constant(igniteSessionId, typeof<string>),
                Expression.Constant(playlistId, typeof<string>),
                Expression.Constant(signalRSessionId, typeof<string>),
                Expression.Constant(null, typeof<PerformContext>),
                Expression.Constant(CancellationToken.None)
            )

        let expression =
            Expression.Lambda<Func<PlaylistSearchJob, Task>>(call, parameter)

        jobClient.Enqueue<PlaylistSearchJob>(expression)

    let acceptedResult (jobId: string) (playlistId: string) (signalRSessionId: string) =
        Results.Accepted(
            value =
                {| jobId = jobId
                   playlistId = playlistId
                   sessionId = signalRSessionId |}
        )
