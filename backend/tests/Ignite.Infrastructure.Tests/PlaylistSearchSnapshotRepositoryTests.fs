module Ignite.Infrastructure.Tests.PlaylistSearchSnapshotRepositoryTests

open System
open System.Threading
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Data
open Ignite.Infrastructure.Data.Repositories
open Microsoft.Data.Sqlite
open Microsoft.EntityFrameworkCore
open Xunit

let private createContextAsync () =
    task {
        let connection = new SqliteConnection("Data Source=:memory:")
        do! connection.OpenAsync()

        let options =
            DbContextOptionsBuilder<IgniteDbContext>()
                .UseSqlite(connection)
                .Options

        let context = new IgniteDbContext(options)
        let! _ = context.Database.EnsureCreatedAsync()
        return connection, context
    }

[<Fact>]
let ``upsert replaces one user playlist snapshot without exposing it to another user`` () =
    task {
        let! connection, context = createContextAsync ()
        use connection = connection
        use context = context
        let repository = PlaylistSearchSnapshotRepository(context) :> IPlaylistSearchSnapshotRepository
        let firstGeneratedAt = DateTime.UtcNow.AddHours(-2.0)

        let first =
            PlaylistSearchSnapshot(
                SpotifyUserId = "spotify-user-1",
                PlaylistId = "playlist-1",
                ResultsJson = "[{\"spotifyTrack\":{\"id\":\"track-1\"}}]",
                TotalTracks = 10,
                ProcessedTracks = 10,
                MatchedTracks = 1,
                TotalMatches = 1,
                DurationTicks = TimeSpan.FromSeconds(2.0).Ticks,
                GeneratedAt = firstGeneratedAt
            )

        let! created = repository.UpsertAsync(first, CancellationToken.None)
        context.ChangeTracker.Clear()

        let replacement =
            PlaylistSearchSnapshot(
                SpotifyUserId = "spotify-user-1",
                PlaylistId = "playlist-1",
                ResultsJson = "[]",
                TotalTracks = 12,
                ProcessedTracks = 12,
                MatchedTracks = 0,
                TotalMatches = 0,
                DurationTicks = TimeSpan.FromSeconds(3.0).Ticks,
                GeneratedAt = DateTime.UtcNow
            )

        let! updated = repository.UpsertAsync(replacement, CancellationToken.None)
        context.ChangeTracker.Clear()
        let! loaded = repository.GetLatestAsync("spotify-user-1", "playlist-1", CancellationToken.None)
        let! otherUser = repository.GetLatestAsync("spotify-user-2", "playlist-1", CancellationToken.None)
        let! snapshotCount = context.PlaylistSearchSnapshots.CountAsync()

        Assert.Equal(created.Id, updated.Id)
        Assert.Equal(1, snapshotCount)
        Assert.Equal(12, loaded.TotalTracks)
        Assert.Equal("[]", loaded.ResultsJson)
        Assert.True(loaded.GeneratedAt > firstGeneratedAt)
        Assert.Null(otherUser)
    }

[<Fact>]
let ``delete by Spotify user removes every matching snapshot and preserves other users`` () =
    task {
        let! connection, context = createContextAsync ()
        use connection = connection
        use context = context
        let repository = PlaylistSearchSnapshotRepository(context) :> IPlaylistSearchSnapshotRepository

        for spotifyUserId, playlistId in
            [ "spotify-user-1", "playlist-1"
              "spotify-user-1", "playlist-2"
              "spotify-user-2", "playlist-1" ] do
            let snapshot =
                PlaylistSearchSnapshot(
                    SpotifyUserId = spotifyUserId,
                    PlaylistId = playlistId,
                    ResultsJson = "[]"
                )

            let! _ = repository.UpsertAsync(snapshot, CancellationToken.None)
            ()

        context.ChangeTracker.Clear()
        do! repository.DeleteBySpotifyUserIdAsync("spotify-user-1", CancellationToken.None)
        context.ChangeTracker.Clear()

        let! deletedUserCount =
            context.PlaylistSearchSnapshots.CountAsync(fun snapshot ->
                snapshot.SpotifyUserId = "spotify-user-1")

        let! retainedUserCount =
            context.PlaylistSearchSnapshots.CountAsync(fun snapshot ->
                snapshot.SpotifyUserId = "spotify-user-2")

        Assert.Equal(0, deletedUserCount)
        Assert.Equal(1, retainedUserCount)
    }
