module Ignite.Infrastructure.Tests.SpotifyPlaylistPaginationTests

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Spotify
open Xunit

let private makeTrack index =
    SpotifyPlaylistTrack(
        SpotifyTrack($"track-{index}", $"Track {index}", [| "Artist" |], "Album", 180000),
        DateTime.UnixEpoch
    )

let private asReadOnly (items: SpotifyPlaylistTrack seq) =
    List<SpotifyPlaylistTrack>(items) :> IReadOnlyList<SpotifyPlaylistTrack>

[<Fact>]
let ``fetches all 691 playlist items across explicit pages`` () =
    task {
        let total = 691
        let offsets = List<int>()

        let fetchPage =
            Func<int, int, CancellationToken, Task<SpotifyPlaylistTrackPage>>(fun offset limit _ ->
                offsets.Add(offset)
                let count = min limit (total - offset)
                let tracks = [ for index in offset .. offset + count - 1 -> makeTrack index ]

                Task.FromResult(
                    SpotifyPlaylistTrackPage(
                        total,
                        offset,
                        count,
                        asReadOnly tracks,
                        offset + count < total
                    )
                ))

        let! result = SpotifyPlaylistPagination.fetchAllAsync fetchPage CancellationToken.None

        Assert.True(result.IsComplete)
        Assert.Equal(total, result.TotalItems)
        Assert.Equal(total, result.RetrievedItems)
        Assert.Equal(total, result.Tracks.Count)
        Assert.Equal(0, result.SkippedItems)
        Assert.Equal(0, result.UnretrievedItems)
        Assert.Equal<int list>([ 0; 50; 100; 150; 200; 250; 300; 350; 400; 450; 500; 550; 600; 650 ], offsets |> Seq.toList)
        Assert.Equal(total, result.Tracks |> Seq.map (fun item -> item.Track.Id) |> Seq.distinct |> Seq.length)
    }

[<Fact>]
let ``accounts for unsupported and unavailable playlist items as skipped`` () =
    task {
        let fetchPage =
            Func<int, int, CancellationToken, Task<SpotifyPlaylistTrackPage>>(fun offset _ _ ->
                Task.FromResult(SpotifyPlaylistTrackPage(3, offset, 3, asReadOnly [ makeTrack 1 ], false)))

        let! result = SpotifyPlaylistPagination.fetchAllAsync fetchPage CancellationToken.None

        Assert.True(result.IsComplete)
        Assert.Equal(3, result.RetrievedItems)
        Assert.Single(result.Tracks) |> ignore
        Assert.Equal(2, result.SkippedItems)
    }

[<Fact>]
let ``preserves earlier pages and a reason when a later page fails`` () =
    task {
        let fetchPage =
            Func<int, int, CancellationToken, Task<SpotifyPlaylistTrackPage>>(fun offset limit _ ->
                if offset = 100 then
                    Task.FromException<SpotifyPlaylistTrackPage>(
                        SpotifyPlaylistPageFetchException(
                            "Spotify stopped returning playlist items at offset 100. Partial results are shown.",
                            InvalidOperationException("upstream failure")
                        )
                    )
                else
                    let tracks = [ for index in offset .. offset + limit - 1 -> makeTrack index ]
                    Task.FromResult(SpotifyPlaylistTrackPage(691, offset, limit, asReadOnly tracks, true)))

        let! result = SpotifyPlaylistPagination.fetchAllAsync fetchPage CancellationToken.None

        Assert.False(result.IsComplete)
        Assert.Equal(100, result.RetrievedItems)
        Assert.Equal(100, result.Tracks.Count)
        Assert.Equal(591, result.UnretrievedItems)
        Assert.Equal(
            "Spotify stopped returning playlist items at offset 100. Partial results are shown.",
            result.FailureReason
        )
    }

[<Fact>]
let ``rejects an early terminal page instead of silently truncating`` () =
    task {
        let fetchPage =
            Func<int, int, CancellationToken, Task<SpotifyPlaylistTrackPage>>(fun offset _ _ ->
                Task.FromResult(
                    SpotifyPlaylistTrackPage(
                        691,
                        offset,
                        50,
                        asReadOnly [ for index in 0..49 -> makeTrack index ],
                        false
                    )
                ))

        let! result = SpotifyPlaylistPagination.fetchAllAsync fetchPage CancellationToken.None

        Assert.False(result.IsComplete)
        Assert.Equal(50, result.RetrievedItems)
        Assert.Equal(641, result.UnretrievedItems)
        Assert.Contains("50 of 691", result.FailureReason)
    }

[<Fact>]
let ``a retried page is appended once without duplicate tracks`` () =
    task {
        let mutable attempts = 0
        let retryAttempts = List<int>()

        let operation =
            Func<CancellationToken, Task<SpotifyPlaylistTrackPage>>(fun _ ->
                attempts <- attempts + 1

                if attempts = 1 then
                    Task.FromException<SpotifyPlaylistTrackPage>(TimeoutException("transient page failure"))
                else
                    Task.FromResult(
                        SpotifyPlaylistTrackPage(1, 0, 1, asReadOnly [ makeTrack 1 ], false)
                    ))

        let retryDelay =
            Func<Exception, Nullable<TimeSpan>>(fun ex ->
                if ex :? TimeoutException then Nullable(TimeSpan.Zero) else Nullable())

        let onRetry =
            Action<int, TimeSpan>(fun attempt _ -> retryAttempts.Add(attempt))

        let fetchPage =
            Func<int, int, CancellationToken, Task<SpotifyPlaylistTrackPage>>(fun _ _ cancellationToken ->
                SpotifyPlaylistPageRetry.executeAsync 3 retryDelay onRetry operation cancellationToken)

        let! result = SpotifyPlaylistPagination.fetchAllAsync fetchPage CancellationToken.None

        Assert.True(result.IsComplete)
        Assert.Equal(2, attempts)
        Assert.Equal<int list>([ 1 ], retryAttempts |> Seq.toList)
        Assert.Single(result.Tracks) |> ignore
        Assert.Equal("track-1", result.Tracks[0].Track.Id)
    }
