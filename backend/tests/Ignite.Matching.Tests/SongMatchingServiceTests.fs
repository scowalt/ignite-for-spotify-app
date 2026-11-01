module Ignite.Matching.Tests.SongMatchingServiceTests

open System
open System.Threading
open System.Threading.Tasks
open Xunit
open NSubstitute
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Microsoft.Extensions.Logging

let private createService () =
    let spotifyClient = Substitute.For<ISpotifyClientService>()
    let logger = Substitute.For<ILogger<Ignite.Matching.SongMatchingService>>()
    let service = Ignite.Matching.SongMatchingService(spotifyClient, logger)
    (service :> ISongMatchingService, spotifyClient)

[<Fact>]
let ``FindSpotifyMatchAsync returns first match`` () =
    task {
        let (service, spotifyClient) = createService ()
        let expectedTrack = SpotifyTrack("123", "Title", [| "Artist" |], "Album", 200000)

        spotifyClient
            .SearchTrackAsync("token", Arg.Any<string>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<SpotifyTrack>(null))
        |> ignore

        spotifyClient
            .SearchTrackAsync("token", "artist:Artist track:Title", Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<SpotifyTrack>(expectedTrack))
        |> ignore

        let! result = service.FindSpotifyMatchAsync("token", "Artist", "Title", null, CancellationToken.None)
        Assert.Equal(expectedTrack, result)
    }

[<Fact>]
let ``FindSpotifyMatchAsync returns null when no match`` () =
    task {
        let (service, spotifyClient) = createService ()

        spotifyClient
            .SearchTrackAsync("token", Arg.Any<string>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<SpotifyTrack>(null))
        |> ignore

        let! result = service.FindSpotifyMatchAsync("token", "Artist", "Title", null, CancellationToken.None)
        Assert.Null(result)
    }

[<Fact>]
let ``FindSpotifyMatchAsync tries next strategy when first fails`` () =
    task {
        let (service, spotifyClient) = createService ()
        let expectedTrack = SpotifyTrack("123", "Title", [| "Artist" |], "Album", 200000)

        spotifyClient
            .SearchTrackAsync("token", "artist:Artist track:Title album:Album", Arg.Any<CancellationToken>())
            .Returns(Task.FromException<SpotifyTrack>(Exception("API error")))
        |> ignore

        spotifyClient
            .SearchTrackAsync("token", "artist:Artist track:Title", Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<SpotifyTrack>(expectedTrack))
        |> ignore

        let! result = service.FindSpotifyMatchAsync("token", "Artist", "Title", "Album", CancellationToken.None)
        Assert.Equal(expectedTrack, result)
    }

[<Fact>]
let ``FindSpotifyMatchAsync short circuits on first match`` () =
    task {
        let (service, spotifyClient) = createService ()
        let expectedTrack = SpotifyTrack("123", "Title", [| "Artist" |], "Album", 200000)

        spotifyClient
            .SearchTrackAsync("token", "artist:Artist track:Title album:Album", Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<SpotifyTrack>(expectedTrack))
        |> ignore

        let! result = service.FindSpotifyMatchAsync("token", "Artist", "Title", "Album", CancellationToken.None)
        Assert.Equal(expectedTrack, result)

        spotifyClient
            .Received(1)
            .SearchTrackAsync("token", Arg.Any<string>(), Arg.Any<CancellationToken>())
        |> ignore
    }

[<Fact>]
let ``MatchSongsToSpotifyAsync returns results for all songs`` () =
    task {
        let (service, spotifyClient) = createService ()

        let songs: Song seq =
            [| Song(Id = 1, Artist = "A", Title = "T1", Album = "Al", DownloadLink = "http://x")
               Song(Id = 2, Artist = "B", Title = "T2", Album = "Al", DownloadLink = "http://x") |]

        spotifyClient
            .SearchTrackAsync("token", Arg.Any<string>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<SpotifyTrack>(null))
        |> ignore

        let! results = service.MatchSongsToSpotifyAsync("token", songs, null, CancellationToken.None)
        Assert.Equal(2, results.Count)

        for r in results do
            Assert.Null(r.MatchStrategy)
    }

[<Fact>]
let ``MatchSongsToSpotifyAsync sets found strategy when matched`` () =
    task {
        let (service, spotifyClient) = createService ()
        let track = SpotifyTrack("123", "Title", [| "Artist" |], "Album", 200000)

        let songs: Song seq =
            [| Song(Id = 1, Artist = "Artist", Title = "Title", Album = "Album", DownloadLink = "http://x") |]

        spotifyClient
            .SearchTrackAsync("token", Arg.Any<string>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<SpotifyTrack>(track))
        |> ignore

        let! results = service.MatchSongsToSpotifyAsync("token", songs, null, CancellationToken.None)
        Assert.Equal("found", results[0].MatchStrategy)
        Assert.Equal(track, results[0].SpotifyMatch)
    }

[<Fact>]
let ``MatchSongsToSpotifyAsync reports progress`` () =
    task {
        let (service, spotifyClient) = createService ()

        let songs: Song seq =
            [| Song(Id = 1, Artist = "A", Title = "T1", Album = "Al", DownloadLink = "http://x")
               Song(Id = 2, Artist = "B", Title = "T2", Album = "Al", DownloadLink = "http://x")
               Song(Id = 3, Artist = "C", Title = "T3", Album = "Al", DownloadLink = "http://x") |]

        spotifyClient
            .SearchTrackAsync("token", Arg.Any<string>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<SpotifyTrack>(null))
        |> ignore

        let progressValues = System.Collections.Generic.List<int>()
        let progress = Substitute.For<IProgress<int>>()

        progress
            .When(fun p -> p.Report(Arg.Any<int>()))
            .Do(fun ci -> progressValues.Add(ci.Arg<int>()))

        let! _ = service.MatchSongsToSpotifyAsync("token", songs, progress, CancellationToken.None)
        Assert.Equal<int list>([ 1; 2; 3 ], progressValues |> Seq.toList)
    }

[<Fact>]
let ``MatchSongsToSpotifyAsync throws on cancellation`` () =
    task {
        let (service, _) = createService ()

        let songs: Song seq =
            [| Song(Id = 1, Artist = "A", Title = "T1", Album = "Al", DownloadLink = "http://x") |]

        let cts = new CancellationTokenSource()
        cts.Cancel()

        let! ex =
            Assert.ThrowsAsync<OperationCanceledException>(fun () ->
                service.MatchSongsToSpotifyAsync("token", songs, null, cts.Token))

        Assert.NotNull(ex)
    }
