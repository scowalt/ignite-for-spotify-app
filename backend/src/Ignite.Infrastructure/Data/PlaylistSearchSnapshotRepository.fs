namespace Ignite.Infrastructure.Data.Repositories

open System.Linq
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Data
open Microsoft.EntityFrameworkCore

type PlaylistSearchSnapshotRepository(context: IgniteDbContext) =
    interface IPlaylistSearchSnapshotRepository with
        member _.GetLatestAsync(spotifyUserId: string, playlistId: string, cancellationToken: CancellationToken) =
            context.PlaylistSearchSnapshots
                .AsNoTracking()
                .SingleOrDefaultAsync(
                    (fun snapshot ->
                        snapshot.SpotifyUserId = spotifyUserId
                        && snapshot.PlaylistId = playlistId),
                    cancellationToken
                )

        member _.UpsertAsync(snapshot: PlaylistSearchSnapshot, cancellationToken: CancellationToken) =
            task {
                let! existing =
                    context.PlaylistSearchSnapshots.SingleOrDefaultAsync(
                        (fun candidate ->
                            candidate.SpotifyUserId = snapshot.SpotifyUserId
                            && candidate.PlaylistId = snapshot.PlaylistId),
                        cancellationToken
                    )

                let saved =
                    if isNull existing then
                        context.PlaylistSearchSnapshots.Add(snapshot) |> ignore
                        snapshot
                    else
                        existing.ResultsJson <- snapshot.ResultsJson
                        existing.TotalTracks <- snapshot.TotalTracks
                        existing.ProcessedTracks <- snapshot.ProcessedTracks
                        existing.MatchedTracks <- snapshot.MatchedTracks
                        existing.TotalMatches <- snapshot.TotalMatches
                        existing.SkippedTracks <- snapshot.SkippedTracks
                        existing.FailedTracks <- snapshot.FailedTracks
                        existing.UnprocessedTracks <- snapshot.UnprocessedTracks
                        existing.DurationTicks <- snapshot.DurationTicks
                        existing.GeneratedAt <- snapshot.GeneratedAt
                        existing

                do! context.SaveChangesAsync(cancellationToken) :> Task
                return saved
            }

        member _.DeleteBySpotifyUserIdAsync(spotifyUserId: string, cancellationToken: CancellationToken) =
            task {
                let! _ =
                    context.PlaylistSearchSnapshots
                        .Where(fun snapshot -> snapshot.SpotifyUserId = spotifyUserId)
                        .ExecuteDeleteAsync(cancellationToken)

                return ()
            }
            :> Task
