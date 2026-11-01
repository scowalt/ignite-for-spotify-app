namespace Ignite.Infrastructure.Spotify

open System
open System.Collections.Generic
open System.Linq
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Interfaces
open Microsoft.Extensions.Logging
open Polly
open Polly.RateLimiting
open Polly.Retry
open SpotifyAPI.Web
open System.Threading.RateLimiting

type SpotifyPlaylistTrackPage
    (
        totalItems: int,
        offset: int,
        itemCount: int,
        tracks: IReadOnlyList<SpotifyPlaylistTrack>,
        hasNext: bool
    ) =
    member _.TotalItems = totalItems
    member _.Offset = offset
    member _.ItemCount = itemCount
    member _.Tracks = tracks
    member _.HasNext = hasNext

type SpotifyPlaylistPageFetchException(userMessage: string, innerException: Exception) =
    inherit Exception(userMessage, innerException)
    member _.UserMessage = userMessage

module SpotifyPlaylistPageRetry =
    let executeAsync
        (maxRetries: int)
        (retryDelay: Func<Exception, Nullable<TimeSpan>>)
        (onRetry: Action<int, TimeSpan>)
        (operation: Func<CancellationToken, Task<'T>>)
        (cancellationToken: CancellationToken)
        =
        let rec execute attempt =
            task {
                try
                    return! operation.Invoke(cancellationToken)
                with ex ->
                    let delay = retryDelay.Invoke(ex)

                    if not delay.HasValue || attempt >= maxRetries then
                        return raise ex
                    else
                        onRetry.Invoke(attempt + 1, delay.Value)

                        if delay.Value > TimeSpan.Zero then
                            do! Task.Delay(delay.Value, cancellationToken)

                        return! execute (attempt + 1)
            }

        execute 0

module SpotifyPlaylistPagination =
    [<Literal>]
    let PageSize = 50

    let fetchAllAsync
        (fetchPageAsync: Func<int, int, CancellationToken, Task<SpotifyPlaylistTrackPage>>)
        (cancellationToken: CancellationToken)
        =
        task {
            let tracks = List<SpotifyPlaylistTrack>()
            let mutable totalItems = 0
            let mutable retrievedItems = 0
            let mutable skippedItems = 0
            let mutable offset = 0
            let mutable keepGoing = true
            let mutable isComplete = true
            let mutable failureReason: string | null = null

            while keepGoing do
                try
                    let! page = fetchPageAsync.Invoke(offset, PageSize, cancellationToken)

                    if retrievedItems = 0 then
                        totalItems <- max 0 page.TotalItems
                    else
                        totalItems <- max totalItems page.TotalItems

                    if page.Offset <> offset then
                        isComplete <- false
                        keepGoing <- false
                        failureReason <-
                            $"Spotify returned playlist items from offset {page.Offset} when offset {offset} was requested."
                    elif page.ItemCount < 0 || page.Tracks.Count > page.ItemCount then
                        isComplete <- false
                        keepGoing <- false
                        failureReason <- "Spotify returned an invalid playlist page."
                    else
                        tracks.AddRange(page.Tracks)
                        retrievedItems <- retrievedItems + page.ItemCount
                        skippedItems <- skippedItems + page.ItemCount - page.Tracks.Count

                        if page.HasNext then
                            if page.ItemCount = 0 then
                                isComplete <- false
                                keepGoing <- false
                                failureReason <-
                                    $"Spotify stopped pagination after {retrievedItems} of {totalItems} playlist items."
                            else
                                offset <- offset + page.ItemCount
                        else
                            keepGoing <- false

                            if retrievedItems < totalItems then
                                isComplete <- false
                                failureReason <-
                                    $"Spotify stopped pagination after {retrievedItems} of {totalItems} playlist items."
                with
                | :? OperationCanceledException ->
                    raise (OperationCanceledException(cancellationToken))
                | :? SpotifyPlaylistPageFetchException as ex ->
                    isComplete <- false
                    keepGoing <- false
                    failureReason <- ex.UserMessage
                | _ ->
                    isComplete <- false
                    keepGoing <- false
                    failureReason <- "Spotify stopped returning playlist items before the playlist was complete."

            return
                SpotifyPlaylistTrackFetchResult(
                    max totalItems retrievedItems,
                    retrievedItems,
                    tracks,
                    skippedItems,
                    isComplete,
                    failureReason
                )
        }

type RateLimitedSpotifyClient(logger: ILogger<RateLimitedSpotifyClient>) =

    let rateLimiter =
        new SlidingWindowRateLimiter(
            SlidingWindowRateLimiterOptions(
                PermitLimit = 5,
                Window = TimeSpan.FromSeconds(1.0),
                SegmentsPerWindow = 1,
                QueueProcessingOrder = QueueProcessingOrder.OldestFirst,
                QueueLimit = 100
            )
        )

    let pipeline =
        ResiliencePipelineBuilder()
            .AddRateLimiter(
                RateLimiterStrategyOptions(
                    RateLimiter = fun args -> rateLimiter.AcquireAsync(1, args.Context.CancellationToken)
                )
            )
            .AddRetry(
                RetryStrategyOptions(
                    MaxRetryAttempts = 3,
                    Delay = TimeSpan.FromSeconds(1.0),
                    BackoffType = DelayBackoffType.Exponential,
                    ShouldHandle = PredicateBuilder().Handle<APITooManyRequestsException>(),
                    OnRetry =
                        fun args ->
                            logger.LogWarning(
                                "Rate limited by Spotify, retrying in {Delay}ms (attempt {Attempt})",
                                args.RetryDelay.TotalMilliseconds,
                                args.AttemptNumber
                            )

                            ValueTask.CompletedTask
                )
            )
            .Build()

    let pagePipeline =
        ResiliencePipelineBuilder()
            .AddRateLimiter(
                RateLimiterStrategyOptions(
                    RateLimiter = fun args -> rateLimiter.AcquireAsync(1, args.Context.CancellationToken)
                )
            )
            .Build()

    let createClient (accessToken: string) = SpotifyClient(accessToken)

    let fetchPlaylistPageAsync
        (client: SpotifyClient)
        (playlistId: string)
        (offset: int)
        (limit: int)
        (cancellationToken: CancellationToken)
        =
        let operation =
            Func<CancellationToken, Task<SpotifyPlaylistTrackPage>>(fun operationCancellationToken ->
                pagePipeline
                    .ExecuteAsync(
                        (fun ct ->
                            ValueTask<SpotifyPlaylistTrackPage>(
                                task {
                                    let request =
                                        PlaylistGetItemsRequest(
                                            PlaylistGetItemsRequest.AdditionalTypes.Track,
                                            Limit = limit,
                                            Offset = offset
                                        )

                                    let! page = client.Playlists.GetPlaylistItems(playlistId, request, ct)
                                    let tracks = List<SpotifyPlaylistTrack>()

                                    for item in page.Items do
                                        if not (isNull item) then
                                            match item.Item with
                                            | :? FullTrack as track
                                                when not (isNull track)
                                                     && not (String.IsNullOrWhiteSpace(track.Id))
                                                     && not (isNull track.Artists)
                                                     && not (isNull track.Album) ->
                                                tracks.Add(
                                                    SpotifyPlaylistTrack(
                                                        SpotifyTrack(
                                                            track.Id,
                                                            track.Name,
                                                            (track.Artists
                                                             |> Seq.map (fun artist -> artist.Name)
                                                             |> Seq.toArray),
                                                            track.Album.Name,
                                                            track.DurationMs
                                                        ),
                                                        (if item.AddedAt.HasValue then
                                                             item.AddedAt.Value
                                                         else
                                                             DateTime.UtcNow)
                                                    )
                                                )
                                            | _ -> ()

                                    return
                                        SpotifyPlaylistTrackPage(
                                            page.Total.GetValueOrDefault(page.Items.Count),
                                            page.Offset.GetValueOrDefault(offset),
                                            page.Items.Count,
                                            tracks,
                                            not (String.IsNullOrEmpty(page.Next))
                                        )
                                }
                            )),
                        operationCancellationToken
                    )
                    .AsTask())

        let retryDelay =
            Func<Exception, Nullable<TimeSpan>>(fun ex ->
                match ex with
                | :? APITooManyRequestsException as rateLimitException ->
                    let delay =
                        if rateLimitException.RetryAfter > TimeSpan.Zero then
                            rateLimitException.RetryAfter
                        else
                            TimeSpan.FromSeconds(1.0)

                    Nullable(delay)
                | _ -> Nullable())

        let onRetry =
            Action<int, TimeSpan>(fun attempt delay ->
                logger.LogWarning(
                    "Rate limited while retrieving playlist {PlaylistId} offset {Offset}; retrying in {Delay}ms (attempt {Attempt})",
                    playlistId,
                    offset,
                    delay.TotalMilliseconds,
                    attempt
                ))

        task {
            try
                return!
                    SpotifyPlaylistPageRetry.executeAsync 3 retryDelay onRetry operation cancellationToken
            with
                | :? APITooManyRequestsException as ex ->
                    return
                        raise (
                            SpotifyPlaylistPageFetchException(
                                "Spotify kept rate limiting this playlist. Partial results are shown; try again later.",
                                ex
                            )
                        )
                | :? APIUnauthorizedException as ex ->
                    return
                        raise (
                            SpotifyPlaylistPageFetchException(
                                "Spotify authorization expired while loading this playlist. Sign in again and retry.",
                                ex
                            )
                        )
                | ex ->
                    logger.LogWarning(ex, "Failed to retrieve playlist {PlaylistId} at offset {Offset}", playlistId, offset)

                    return
                        raise (
                            SpotifyPlaylistPageFetchException(
                                $"Spotify stopped returning playlist items at offset {offset}. Partial results are shown.",
                                ex
                            )
                        )
        }

    interface ISpotifyClientService with
        member _.GetUserPlaylistsAsync(accessToken: string, cancellationToken: CancellationToken) =
            task {
                let client = createClient accessToken
                let playlists = List<SpotifyPlaylist>()

                do!
                    pipeline.ExecuteAsync(
                        (fun ct ->
                            ValueTask(
                                task {
                                    let! page = client.Playlists.CurrentUsers(ct)

                                    let enumerator =
                                        client.Paginate(page).GetAsyncEnumerator(ct)

                                    let mutable hasMore = true

                                    while hasMore do
                                        let! moveNext = enumerator.MoveNextAsync()
                                        hasMore <- moveNext

                                        if hasMore then
                                            let playlist = enumerator.Current

                                            playlists.Add(
                                                SpotifyPlaylist(
                                                    playlist.Id,
                                                    playlist.Name,
                                                    playlist.Description,
                                                    (if isNull playlist.Items then
                                                         0
                                                     else
                                                         playlist.Items.Total.GetValueOrDefault(0)),
                                                    (if isNull playlist.Images || playlist.Images.Count = 0 then
                                                         null
                                                     else
                                                         playlist.Images.First().Url)
                                                )
                                            )

                                    do! enumerator.DisposeAsync().AsTask()
                                }
                            )),
                        cancellationToken
                    )

                return playlists :> IReadOnlyList<SpotifyPlaylist>
            }

        member _.GetPlaylistAsync(accessToken: string, playlistId: string, cancellationToken: CancellationToken) =
            task {
                let client = createClient accessToken

                return!
                    pipeline.ExecuteAsync(
                        (fun ct ->
                            ValueTask<SpotifyPlaylist>(
                                task {
                                    let! playlist = client.Playlists.Get(playlistId, ct)

                                    return
                                        SpotifyPlaylist(
                                            playlist.Id,
                                            playlist.Name,
                                            playlist.Description,
                                            (if isNull playlist.Items then
                                                 0
                                             else
                                                 playlist.Items.Total.GetValueOrDefault(0)),
                                            (if isNull playlist.Images || playlist.Images.Count = 0 then
                                                 null
                                             else
                                                 playlist.Images.First().Url)
                                        )
                                }
                            )),
                        cancellationToken
                    )
            }

        member _.GetPlaylistTracksAsync
            (
                accessToken: string,
                playlistId: string,
                cancellationToken: CancellationToken
            ) =
            task {
                let client = createClient accessToken

                let fetchPage =
                    Func<int, int, CancellationToken, Task<SpotifyPlaylistTrackPage>>(fun offset limit ct ->
                        fetchPlaylistPageAsync client playlistId offset limit ct)

                return! SpotifyPlaylistPagination.fetchAllAsync fetchPage cancellationToken
            }

        member _.SearchTrackAsync(accessToken: string, query: string, cancellationToken: CancellationToken) =
            task {
                if String.IsNullOrWhiteSpace(query) then
                    return null
                else
                    let client = createClient accessToken

                    return!
                        pipeline.ExecuteAsync(
                            (fun ct ->
                                ValueTask<SpotifyTrack>(
                                    task {
                                        let searchRequest =
                                            SearchRequest(SearchRequest.Types.Track, query, Limit = 1)

                                        let! result = client.Search.Item(searchRequest, ct)
                                        let track = result.Tracks.Items |> Seq.tryHead

                                        match track with
                                        | None -> return null
                                        | Some t ->
                                            return
                                                SpotifyTrack(
                                                    t.Id,
                                                    t.Name,
                                                    (t.Artists |> Seq.map (fun a -> a.Name) |> Seq.toArray),
                                                    t.Album.Name,
                                                    t.DurationMs
                                                )
                                    }
                                )),
                            cancellationToken
                        )
            }

        member _.CreatePlaylistAsync
            (
                accessToken: string,
                name: string,
                description: string | null,
                isPublic: bool,
                cancellationToken: CancellationToken
            ) =
            task {
                let client = createClient accessToken

                return!
                    pipeline.ExecuteAsync(
                        (fun ct ->
                            ValueTask<SpotifyPlaylist>(
                                task {
                                    let request =
                                        PlaylistCreateRequest(name, Description = description, Public = isPublic)

                                    let! playlist = client.Playlists.Create(request, ct)

                                    return
                                        SpotifyPlaylist(
                                            playlist.Id,
                                            playlist.Name,
                                            playlist.Description,
                                            (if isNull playlist.Items then
                                                 0
                                             else
                                                 playlist.Items.Total.GetValueOrDefault(0)),
                                            (if isNull playlist.Images || playlist.Images.Count = 0 then
                                                 null
                                             else
                                                 playlist.Images.First().Url)
                                        )
                                }
                            )),
                        cancellationToken
                    )
            }

        member _.AddTracksToPlaylistAsync
            (
                accessToken: string,
                playlistId: string,
                trackIds: IEnumerable<string>,
                cancellationToken: CancellationToken
            ) =
            task {
                let client = createClient accessToken
                let uris = trackIds |> Seq.map (fun id -> $"spotify:track:{id}") |> Seq.toArray

                for batch in uris.Chunk(100) do
                    do!
                        pipeline.ExecuteAsync(
                            (fun ct ->
                                ValueTask(
                                    task {
                                        let request = PlaylistAddItemsRequest(ResizeArray(batch))
                                        do! client.Playlists.AddPlaylistItems(playlistId, request, ct) :> Task
                                    }
                                )),
                            cancellationToken
                        )
            }
            :> Task
