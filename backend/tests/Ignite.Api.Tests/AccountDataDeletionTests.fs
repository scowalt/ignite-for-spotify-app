module Ignite.Api.Tests.AccountDataDeletionTests

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks
open Ignite.Api
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open NSubstitute
open Xunit

let private createRepositories () =
    Substitute.For<IUserSessionRepository>(),
    Substitute.For<IPlaylistSearchSnapshotRepository>()

[<Fact>]
let ``connected data deletion removes snapshots before the session`` () =
    task {
        let sessionRepository, snapshotRepository = createRepositories ()
        let session = UserSession(Id = "session-1", SpotifyUserId = "spotify-user-1")
        let callOrder = List<string>()

        sessionRepository
            .GetByIdAsync("session-1", Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(session))
        |> ignore

        snapshotRepository
            .DeleteBySpotifyUserIdAsync("spotify-user-1", Arg.Any<CancellationToken>())
            .Returns(fun _ ->
                callOrder.Add("snapshots")
                Task.CompletedTask)
        |> ignore

        sessionRepository
            .DeleteAsync("session-1", Arg.Any<CancellationToken>())
            .Returns(fun _ ->
                callOrder.Add("session")
                Task.CompletedTask)
        |> ignore

        do!
            SessionHelper.deleteConnectedDataAsync
                "session-1"
                sessionRepository
                snapshotRepository
                CancellationToken.None

        Assert.Equal<string list>([ "snapshots"; "session" ], callOrder |> Seq.toList)

        snapshotRepository
            .Received(1)
            .DeleteBySpotifyUserIdAsync("spotify-user-1", Arg.Any<CancellationToken>())
        |> ignore

        sessionRepository
            .Received(1)
            .DeleteAsync("session-1", Arg.Any<CancellationToken>())
        |> ignore
    }

[<Fact>]
let ``connected data deletion uses the legacy session identifier when Spotify user id is absent`` () =
    task {
        let sessionRepository, snapshotRepository = createRepositories ()
        let session = UserSession(Id = "legacy-session", SpotifyUserId = null)

        sessionRepository
            .GetByIdAsync("legacy-session", Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(session))
        |> ignore

        do!
            SessionHelper.deleteConnectedDataAsync
                "legacy-session"
                sessionRepository
                snapshotRepository
                CancellationToken.None

        snapshotRepository
            .Received(1)
            .DeleteBySpotifyUserIdAsync("legacy-session", Arg.Any<CancellationToken>())
        |> ignore
    }

[<Fact>]
let ``connected data deletion is idempotent when the session is missing`` () =
    task {
        let sessionRepository, snapshotRepository = createRepositories ()

        sessionRepository
            .GetByIdAsync("missing-session", Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<UserSession>(null))
        |> ignore

        do!
            SessionHelper.deleteConnectedDataAsync
                "missing-session"
                sessionRepository
                snapshotRepository
                CancellationToken.None

        snapshotRepository
            .DidNotReceive()
            .DeleteBySpotifyUserIdAsync(Arg.Any<string>(), Arg.Any<CancellationToken>())
        |> ignore

        sessionRepository
            .DidNotReceive()
            .DeleteAsync(Arg.Any<string>(), Arg.Any<CancellationToken>())
        |> ignore
    }

[<Fact>]
let ``snapshot deletion failure preserves the session for retry`` () =
    task {
        let sessionRepository, snapshotRepository = createRepositories ()
        let session = UserSession(Id = "session-1", SpotifyUserId = "spotify-user-1")
        let failure = InvalidOperationException("snapshot store unavailable")

        sessionRepository
            .GetByIdAsync("session-1", Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(session))
        |> ignore

        snapshotRepository
            .DeleteBySpotifyUserIdAsync("spotify-user-1", Arg.Any<CancellationToken>())
            .Returns(Task.FromException(failure))
        |> ignore

        let! caught =
            Assert.ThrowsAsync<InvalidOperationException>(fun () ->
                SessionHelper.deleteConnectedDataAsync
                    "session-1"
                    sessionRepository
                    snapshotRepository
                    CancellationToken.None)

        Assert.Same(failure, caught)

        sessionRepository
            .DidNotReceive()
            .DeleteAsync(Arg.Any<string>(), Arg.Any<CancellationToken>())
        |> ignore
    }
