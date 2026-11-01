namespace Ignite.Infrastructure.Data.Repositories

open System
open System.Collections.Generic
open System.Linq
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Data
open Microsoft.EntityFrameworkCore
open Polly
open Polly.Retry
open System.Runtime.ExceptionServices

type SongRepository(context: IgniteDbContext) =

    let retryPipeline =
        ResiliencePipelineBuilder()
            .AddRetry(
                RetryStrategyOptions(
                    MaxRetryAttempts = 5,
                    Delay = TimeSpan.FromSeconds(2.0),
                    BackoffType = DelayBackoffType.Exponential,
                    ShouldHandle =
                        PredicateBuilder()
                            .Handle<Exception>(fun ex ->
                                ex.Message.Contains("database is locked", StringComparison.OrdinalIgnoreCase)
                                || ex.Message.Contains("connection", StringComparison.OrdinalIgnoreCase)
                                || ex.Message.Contains(
                                    "Error in SQL execution",
                                    StringComparison.OrdinalIgnoreCase
                                )
                                || ex :? Microsoft.Data.Sqlite.SqliteException
                                || ex :? TaskCanceledException
                                || ex :? OperationCanceledException),
                    OnRetry = fun _ ->
                        context.ChangeTracker.Clear()
                        ValueTask.CompletedTask
                )
            )
            .Build()

    interface ISongRepository with
        member _.GetByIdAsync(id: int, cancellationToken: CancellationToken) =
            task { return! context.Songs.FindAsync([| id :> obj |], cancellationToken).AsTask() }

        member _.FindByUniqueKeyAsync
            (
                artist: string,
                title: string,
                author: string | null,
                version: string | null,
                cancellationToken: CancellationToken
            ) =
            task {
                return!
                    context.Songs.FirstOrDefaultAsync(
                        (fun s -> s.Artist = artist && s.Title = title && s.Author = author && s.Version = version),
                        cancellationToken
                    )
            }

        member _.SearchAsync
            (
                filter: SongSearchFilter,
                page: int,
                pageSize: int,
                cancellationToken: CancellationToken
            ) =
            task {
                return!
                    retryPipeline.ExecuteAsync(
                        (fun ct ->
                            ValueTask<PagedResult<Song>>(
                                task {
                                    let mutable query = context.Songs.AsQueryable()

                                    if not (String.IsNullOrWhiteSpace(filter.Artist)) then
                                        let artistLower = filter.Artist.ToLowerInvariant()
                                        query <- query.Where(fun s -> s.Artist.ToLower().Contains(artistLower))

                                    if not (String.IsNullOrWhiteSpace(filter.Title)) then
                                        let titleLower = filter.Title.ToLowerInvariant()
                                        query <- query.Where(fun s -> s.Title.ToLower().Contains(titleLower))

                                    if not (String.IsNullOrWhiteSpace(filter.Album)) then
                                        let albumLower = filter.Album.ToLowerInvariant()
                                        query <- query.Where(fun s -> s.Album.ToLower().Contains(albumLower))

                                    if not (String.IsNullOrWhiteSpace(filter.Author)) then
                                        let authorLower = filter.Author.ToLowerInvariant()

                                        query <-
                                            query.Where(fun s ->
                                                s.Author <> null && s.Author.ToLower().Contains(authorLower))

                                    if filter.Lead.HasValue then
                                        let lead = filter.Lead.Value
                                        query <- query.Where(fun s -> s.Lead = lead)

                                    if filter.Rhythm.HasValue then
                                        let rhythm = filter.Rhythm.Value
                                        query <- query.Where(fun s -> s.Rhythm = rhythm)

                                    if filter.Bass.HasValue then
                                        let bass = filter.Bass.Value
                                        query <- query.Where(fun s -> s.Bass = bass)

                                    if filter.Vocals.HasValue then
                                        let vocals = filter.Vocals.Value
                                        query <- query.Where(fun s -> s.Vocals = vocals)

                                    if filter.DynamicDifficulty.HasValue then
                                        let dynamicDifficulty = filter.DynamicDifficulty.Value
                                        query <- query.Where(fun s -> s.DynamicDifficulty = dynamicDifficulty)

                                    if filter.HasSpotifyId.HasValue then
                                        let hasSpotifyId = filter.HasSpotifyId.Value

                                        query <-
                                            if hasSpotifyId then
                                                query.Where(fun s -> s.SpotifyTrackId <> null)
                                            else
                                                query.Where(fun s -> s.SpotifyTrackId = null)

                                    let! totalCount = query.CountAsync(ct)

                                    let! items =
                                        query
                                            .OrderBy(fun s -> s.Artist)
                                            .ThenBy(fun s -> s.Title)
                                            .Skip((page - 1) * pageSize)
                                            .Take(pageSize)
                                            .ToListAsync(ct)

                                    return PagedResult<Song>(items, totalCount, page, pageSize)
                                }
                            )),
                        cancellationToken
                    )
            }

        member _.GetBySpotifyTrackIdsAsync
            (
                spotifyTrackIds: IEnumerable<string>,
                cancellationToken: CancellationToken
            ) =
            task {
                let ids = spotifyTrackIds |> Seq.toList

                if ids.IsEmpty then
                    return [] :> IReadOnlyList<Song>
                else
                    let results = List<Song>()

                    for id in ids do
                        let! song =
                            context.Songs.FirstOrDefaultAsync((fun s -> s.SpotifyTrackId = id), cancellationToken)

                        if not (isNull song) then
                            results.Add(song)

                    return results :> IReadOnlyList<Song>
            }

        member _.GetSongsWithoutSpotifyIdAsync(limit: int, cancellationToken: CancellationToken) =
            task {
                let! results =
                    context.Songs
                        .Where(fun s -> s.SpotifyTrackId = null)
                        .OrderBy(fun s -> s.Id)
                        .Take(limit)
                        .ToListAsync(cancellationToken)

                return results :> IReadOnlyList<Song>
            }

        member _.CreateAsync(song: Song, cancellationToken: CancellationToken) =
            task {
                context.Songs.Add(song) |> ignore
                do! context.SaveChangesAsync(cancellationToken) :> Task
                return song
            }

        member _.UpdateAsync(song: Song, cancellationToken: CancellationToken) =
            task {
                context.Songs.Update(song) |> ignore
                do! context.SaveChangesAsync(cancellationToken) :> Task
                return song
            }

        member _.UpsertAsync(song: Song, cancellationToken: CancellationToken) =
            task {
                let! existing =
                    context.Songs.FirstOrDefaultAsync(
                        (fun s ->
                            s.Artist = song.Artist
                            && s.Title = song.Title
                            && s.Author = song.Author
                            && s.Version = song.Version),
                        cancellationToken
                    )

                if not (isNull existing) then
                    existing.Album <- song.Album
                    existing.Tuning <- song.Tuning
                    existing.DateAddedToCdlc <- song.DateAddedToCdlc
                    existing.DateUpdatedInCdlc <- song.DateUpdatedInCdlc
                    existing.Lead <- song.Lead
                    existing.Rhythm <- song.Rhythm
                    existing.Bass <- song.Bass
                    existing.Vocals <- song.Vocals
                    existing.DynamicDifficulty <- song.DynamicDifficulty
                    existing.OfficialDlc <- song.OfficialDlc
                    existing.DownloadLink <- song.DownloadLink

                    if isNull existing.SpotifyTrackId && not (isNull song.SpotifyTrackId) then
                        existing.SpotifyTrackId <- song.SpotifyTrackId

                    do! context.SaveChangesAsync(cancellationToken) :> Task
                    return existing.Id
                else
                    context.Songs.Add(song) |> ignore
                    do! context.SaveChangesAsync(cancellationToken) :> Task
                    return song.Id
            }

        member _.BulkUpsertAsync(songs: IEnumerable<Song>, cancellationToken: CancellationToken) =
            task {
                let songList = songs |> Seq.toList

                if songList.IsEmpty then
                    return struct (0, 0)
                else
                    return!
                        retryPipeline.ExecuteAsync(
                            (fun ct ->
                                ValueTask<struct (int * int)>(
                                    task {
                                        let! transaction = context.Database.BeginTransactionAsync(ct)

                                        try
                                            let artists = songList |> List.map (fun s -> s.Artist) |> List.distinct
                                            let existingSongs = List<Song>()

                                            for artist in artists do
                                                let! artistSongs =
                                                    context.Songs
                                                        .Where(fun s -> s.Artist = artist)
                                                        .ToListAsync(ct)

                                                existingSongs.AddRange(artistSongs)

                                            let existingLookup =
                                                existingSongs
                                                |> Seq.map (fun s ->
                                                    (s.Artist, s.Title, (s.Author |> Option.ofObj |> Option.defaultValue ""), (s.Version |> Option.ofObj |> Option.defaultValue "")),
                                                    s)
                                                |> dict

                                            let toAdd = List<Song>()
                                            let mutable updated = 0

                                            for song in songList do
                                                let key =
                                                    (song.Artist, song.Title, (song.Author |> Option.ofObj |> Option.defaultValue ""), (song.Version |> Option.ofObj |> Option.defaultValue ""))

                                                match existingLookup.TryGetValue(key) with
                                                | true, existing ->
                                                    existing.Album <- song.Album
                                                    existing.Tuning <- song.Tuning
                                                    existing.DateUpdatedInCdlc <- song.DateUpdatedInCdlc
                                                    existing.Lead <- song.Lead
                                                    existing.Rhythm <- song.Rhythm
                                                    existing.Bass <- song.Bass
                                                    existing.Vocals <- song.Vocals
                                                    existing.DynamicDifficulty <- song.DynamicDifficulty
                                                    existing.OfficialDlc <- song.OfficialDlc
                                                    existing.DownloadLink <- song.DownloadLink
                                                    updated <- updated + 1
                                                | _ -> toAdd.Add(song)

                                            if toAdd.Count > 0 then
                                                context.Songs.AddRange(toAdd)

                                            do! context.SaveChangesAsync(ct) :> Task
                                            do! transaction.CommitAsync(ct)
                                            let result = struct (toAdd.Count, updated)
                                            context.ChangeTracker.Clear()
                                            return result
                                        with ex ->
                                            do! transaction.RollbackAsync(ct)
                                            context.ChangeTracker.Clear()
                                            ExceptionDispatchInfo.Capture(ex).Throw()
                                            return struct (0, 0)
                                    }
                                )),
                            cancellationToken
                        )
            }

        member _.GetStatsAsync(cancellationToken: CancellationToken) =
            task {
                let! total = context.Songs.CountAsync(cancellationToken)

                let! withSpotify =
                    context.Songs.CountAsync((fun s -> s.SpotifyTrackId <> null), cancellationToken)

                return struct (total, withSpotify)
            }

        member _.FullTextSearchAsync(query: string, limit: int, cancellationToken: CancellationToken) =
            task {
                if String.IsNullOrWhiteSpace(query) then
                    return [] :> IReadOnlyList<Song>
                else
                    let sanitizedQuery =
                        query.Replace("\"", "\"\"").Replace("*", "").Replace(":", "").Trim()

                    if String.IsNullOrEmpty(sanitizedQuery) then
                        return [] :> IReadOnlyList<Song>
                    else
                        let ftsQuery = $"\"{sanitizedQuery}\"*"

                        let! songIds =
                            context.Database
                                .SqlQueryRaw<int>(
                                    "SELECT rowid FROM songs_fts WHERE songs_fts MATCH {0} LIMIT {1}",
                                    ftsQuery,
                                    limit
                                )
                                .ToListAsync(cancellationToken)

                        if songIds.Count = 0 then
                            return [] :> IReadOnlyList<Song>
                        else
                            let results = List<Song>()

                            for id in songIds do
                                let! song = context.Songs.FindAsync([| id :> obj |], cancellationToken)

                                if not (isNull song) then
                                    results.Add(song)

                            return results :> IReadOnlyList<Song>
            }
