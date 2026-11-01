module Ignite.Api.Tests.PlaylistSearchJobTests

#nowarn "3261"

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks
open Hangfire
open Hangfire.Common
open Hangfire.States
open Ignite.Api
open Ignite.Api.Hubs
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Microsoft.Extensions.Logging
open Microsoft.AspNetCore.Http
open NSubstitute
open Xunit

type Completion =
    { TotalTracks: int
      ProcessedTracks: int
      MatchedTracks: int
      TotalMatches: int
      SkippedTracks: int
      FailedTracks: int
      UnprocessedTracks: int
      IsComplete: bool
      FailureReason: string | null }

type FakeNotifications() =
    let progress = List<int>()
    let mutable resultCount = 0
    let mutable completion: Completion option = None
    let errors = List<string>()
    let resultMatches = List<IEnumerable<CdlcMatchInfo>>()

    member _.Progress = progress :> IReadOnlyList<int>
    member _.ResultCount = resultCount
    member _.Completion = completion
    member _.Errors = errors :> IReadOnlyList<string>
    member _.ResultMatches = resultMatches :> IReadOnlyList<IEnumerable<CdlcMatchInfo>>

    interface IHubNotificationService with
        member _.SendSearchProgressAsync(_, processed, _, _) =
            progress.Add(processed)
            Task.CompletedTask

        member _.SendSearchResultAsync(_, _, matches) =
            resultCount <- resultCount + 1
            resultMatches.Add(matches)
            Task.CompletedTask

        member _.SendSearchCompleteAsync(_, total, processed, matched, matches, skipped, failed, unprocessed, isComplete, reason, _) =
            completion <-
                Some
                    { TotalTracks = total
                      ProcessedTracks = processed
                      MatchedTracks = matched
                      TotalMatches = matches
                      SkippedTracks = skipped
                      FailedTracks = failed
                      UnprocessedTracks = unprocessed
                      IsComplete = isComplete
                      FailureReason = reason }

            Task.CompletedTask

        member _.SendJobProgressAsync(_, _, _, _, _, _, _) = Task.CompletedTask
        member _.SendJobCompleteAsync(_, _, _, _, _, _, _, _) = Task.CompletedTask

        member _.SendErrorAsync(_, message, ?details) =
            errors.Add(message)
            Task.CompletedTask

let private makePlaylistTrack index =
    SpotifyPlaylistTrack(
        SpotifyTrack($"track-{index}", $"Track {index}", [| "Artist" |], "Album", 180000),
        DateTime.UnixEpoch
    )

let private makeMatch index =
    Song(
        Id = index,
        Artist = "Artist",
        Title = $"Track {index}",
        Album = "Album",
        OfficialDlc = (index = 2),
        DownloadLink = $"https://example.test/{index}"
    )

let private createSessionJob (session: UserSession | null) =
    let spotifyClient = Substitute.For<ISpotifyClientService>()
    let songRepository = Substitute.For<ISongRepository>()
    let authService = Substitute.For<ISpotifyAuthService>()
    let sessionRepository = Substitute.For<IUserSessionRepository>()
    let snapshotRepository = Substitute.For<IPlaylistSearchSnapshotRepository>()
    let logger = Substitute.For<ILogger<PlaylistSearchJob>>()
    let notifications = FakeNotifications()
    let tracks = List<SpotifyPlaylistTrack>() :> IReadOnlyList<SpotifyPlaylistTrack>
    let fetchResult = SpotifyPlaylistTrackFetchResult(0, 0, tracks, 0, true, null)

    sessionRepository
        .GetByIdAsync("ignite-session", Arg.Any<CancellationToken>())
        .Returns(Task.FromResult(session))
    |> ignore

    sessionRepository
        .UpdateAsync(Arg.Any<UserSession>(), Arg.Any<CancellationToken>())
        .Returns(fun call -> Task.FromResult(call.ArgAt<UserSession>(0)))
    |> ignore

    spotifyClient
        .GetPlaylistTracksAsync(Arg.Any<string>(), "playlist", Arg.Any<CancellationToken>())
        .Returns(Task.FromResult(fetchResult))
    |> ignore

    snapshotRepository
        .UpsertAsync(Arg.Any<PlaylistSearchSnapshot>(), Arg.Any<CancellationToken>())
        .Returns(fun call -> Task.FromResult(call.ArgAt<PlaylistSearchSnapshot>(0)))
    |> ignore

    let job =
        PlaylistSearchJob(
            spotifyClient,
            songRepository,
            authService,
            sessionRepository,
            snapshotRepository,
            notifications,
            logger
        )

    job, spotifyClient, authService, sessionRepository, notifications, snapshotRepository

let private createJob (fetchResult: SpotifyPlaylistTrackFetchResult) (failedTitle: string option) =
    let spotifyClient = Substitute.For<ISpotifyClientService>()
    let songRepository = Substitute.For<ISongRepository>()
    let authService = Substitute.For<ISpotifyAuthService>()
    let sessionRepository = Substitute.For<IUserSessionRepository>()
    let snapshotRepository = Substitute.For<IPlaylistSearchSnapshotRepository>()
    let logger = Substitute.For<ILogger<PlaylistSearchJob>>()
    let notifications = FakeNotifications()
    let session =
        UserSession(
            Id = "ignite-session",
            SpotifyUserId = "spotify-user",
            SpotifyAccessToken = "token"
        )

    sessionRepository
        .GetByIdAsync("ignite-session", Arg.Any<CancellationToken>())
        .Returns(Task.FromResult(session))
    |> ignore

    spotifyClient
        .GetPlaylistTracksAsync("token", "playlist", Arg.Any<CancellationToken>())
        .Returns(Task.FromResult(fetchResult))
    |> ignore

    songRepository
        .SearchAsync(
            Arg.Any<SongSearchFilter>(),
            1,
            10,
            Arg.Any<CancellationToken>()
        )
        .Returns(fun call ->
            let filter = call.ArgAt<SongSearchFilter>(0)

            if failedTitle = Some filter.Title then
                Task.FromException<PagedResult<Song>>(InvalidOperationException("database unavailable"))
            else
                let index = Int32.Parse(filter.Title.Replace("Track ", ""))
                let items = List<Song>([ makeMatch index ]) :> IReadOnlyList<Song>
                Task.FromResult(PagedResult<Song>(items, 1, 1, 10)))
    |> ignore

    snapshotRepository
        .UpsertAsync(Arg.Any<PlaylistSearchSnapshot>(), Arg.Any<CancellationToken>())
        .Returns(fun call -> Task.FromResult(call.ArgAt<PlaylistSearchSnapshot>(0)))
    |> ignore

    let job =
        PlaylistSearchJob(
            spotifyClient,
            songRepository,
            authService,
            sessionRepository,
            snapshotRepository,
            notifications,
            logger
        )

    job, songRepository, notifications, snapshotRepository

[<Fact>]
let ``processes every available track in a 691 item playlist`` () =
    task {
        let tracks = List<SpotifyPlaylistTrack>([ for index in 1..689 -> makePlaylistTrack index ])
        let fetchResult = SpotifyPlaylistTrackFetchResult(691, 691, tracks, 2, true, null)
        let job, _, notifications, _ = createJob fetchResult None

        do! job.ExecuteAsync("ignite-session", "playlist", "signalr-session", null, CancellationToken.None)

        let completion = notifications.Completion.Value
        Assert.Equal(691, completion.TotalTracks)
        Assert.Equal(689, completion.ProcessedTracks)
        Assert.Equal(689, completion.MatchedTracks)
        Assert.Equal(2, completion.SkippedTracks)
        Assert.Equal(0, completion.FailedTracks)
        Assert.Equal(0, completion.UnprocessedTracks)
        Assert.True(completion.IsComplete)
        Assert.Equal(689, notifications.Progress.Count)
        Assert.Equal(689, notifications.ResultCount)
        Assert.Empty(notifications.Errors)
    }

[<Fact>]
let ``flags official DLC matches in the search result payload`` () =
    task {
        let tracks = List<SpotifyPlaylistTrack>([ for index in 1..2 -> makePlaylistTrack index ])
        let fetchResult = SpotifyPlaylistTrackFetchResult(2, 2, tracks, 0, true, null)
        let job, _, notifications, _ = createJob fetchResult None

        do! job.ExecuteAsync("ignite-session", "playlist", "signalr-session", null, CancellationToken.None)

        Assert.Equal(2, notifications.ResultCount)

        let allMatches = notifications.ResultMatches |> Seq.concat |> Seq.toList
        Assert.Equal(2, allMatches.Length)
        Assert.False(allMatches.[0].OfficialDlc)
        Assert.True(allMatches.[1].OfficialDlc)
    }

[<Fact>]
let ``retains results and reports a partial summary when one match lookup fails`` () =
    task {
        let tracks = List<SpotifyPlaylistTrack>([ for index in 1..3 -> makePlaylistTrack index ])
        let fetchResult = SpotifyPlaylistTrackFetchResult(3, 3, tracks, 0, true, null)
        let job, _, notifications, snapshotRepository = createJob fetchResult (Some "Track 2")

        do! job.ExecuteAsync("ignite-session", "playlist", "signalr-session", null, CancellationToken.None)

        let completion = notifications.Completion.Value
        Assert.Equal(3, completion.ProcessedTracks)
        Assert.Equal(2, completion.MatchedTracks)
        Assert.Equal(1, completion.FailedTracks)
        Assert.Equal(0, completion.UnprocessedTracks)
        Assert.False(completion.IsComplete)
        Assert.Contains("1 track search attempt", completion.FailureReason)
        Assert.Equal(2, notifications.ResultCount)

        snapshotRepository
            .DidNotReceive()
            .UpsertAsync(Arg.Any<PlaylistSearchSnapshot>(), Arg.Any<CancellationToken>())
        |> ignore
    }

[<Fact>]
let ``saves the latest fully completed playlist results for the Spotify user`` () =
    task {
        let tracks = List<SpotifyPlaylistTrack>([ for index in 1..2 -> makePlaylistTrack index ])
        let fetchResult = SpotifyPlaylistTrackFetchResult(2, 2, tracks, 0, true, null)
        let job, _, _, snapshotRepository = createJob fetchResult None

        do! job.ExecuteAsync("ignite-session", "playlist", "signalr-session", null, CancellationToken.None)

        snapshotRepository
            .Received(1)
            .UpsertAsync(
                Arg.Is<PlaylistSearchSnapshot>(fun (snapshot: PlaylistSearchSnapshot) ->
                    snapshot.SpotifyUserId = "spotify-user"
                    && snapshot.PlaylistId = "playlist"
                    && snapshot.MatchedTracks = 2
                    && snapshot.TotalMatches = 2
                    && snapshot.ResultsJson.Contains("track-1")
                    && snapshot.GeneratedAt <= DateTime.UtcNow),
                Arg.Any<CancellationToken>()
            )
        |> ignore
    }

[<Fact>]
let ``refreshes an expired stored session before fetching playlist tracks`` () =
    task {
        let session =
            UserSession(
                Id = "ignite-session",
                SpotifyAccessToken = "old-token",
                SpotifyRefreshToken = "refresh-token",
                TokenExpiresAt = Nullable(DateTime.UtcNow.AddMinutes(-1.0))
            )

        let job, spotifyClient, authService, sessionRepository, notifications, _ =
            createSessionJob session

        let refreshedExpiry = DateTime.UtcNow.AddHours(1.0)

        authService
            .RefreshTokenAsync("refresh-token", Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(SpotifyTokens("new-token", "new-refresh-token", refreshedExpiry)))
        |> ignore

        do! job.ExecuteAsync("ignite-session", "playlist", "signalr-session", null, CancellationToken.None)

        authService.Received(1).RefreshTokenAsync("refresh-token", Arg.Any<CancellationToken>())
        |> ignore

        sessionRepository.Received(1).UpdateAsync(session, Arg.Any<CancellationToken>())
        |> ignore

        spotifyClient.Received(1).GetPlaylistTracksAsync("new-token", "playlist", Arg.Any<CancellationToken>())
        |> ignore

        Assert.Empty(notifications.Errors)
        Assert.True(notifications.Completion.Value.IsComplete)
    }

[<Fact>]
let ``reports a missing stored session without failing the background job`` () =
    task {
        let job, spotifyClient, _, _, notifications, _ = createSessionJob null

        do! job.ExecuteAsync("ignite-session", "playlist", "signalr-session", null, CancellationToken.None)

        spotifyClient
            .DidNotReceive()
            .GetPlaylistTracksAsync(Arg.Any<string>(), Arg.Any<string>(), Arg.Any<CancellationToken>())
        |> ignore

        Assert.Single(notifications.Errors) |> ignore
        Assert.Contains("Spotify session expired", notifications.Errors.[0])
    }

[<Fact>]
let ``enqueue returns immediately with an accepted job response`` () =
    let jobClient = Substitute.For<IBackgroundJobClient>()
    let mutable enqueuedJob: Job | null = null

    jobClient
        .Create(Arg.Do<Job>(fun job -> enqueuedJob <- job), Arg.Any<IState>())
        .Returns("job-123")
    |> ignore

    let jobId =
        PlaylistSearchQueue.enqueue jobClient "ignite-session" "playlist" "signalr-session"

    let result =
        PlaylistSearchQueue.acceptedResult jobId "playlist" "signalr-session"

    Assert.Equal("job-123", jobId)
    Assert.Equal(202, (result :?> IStatusCodeHttpResult).StatusCode.Value)
    Assert.Equal("ignite-session", enqueuedJob.Args.[0] :?> string)
    jobClient.Received(1).Create(Arg.Any<Job>(), Arg.Any<IState>()) |> ignore
