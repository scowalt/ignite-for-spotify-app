namespace Ignite.Matching

#nowarn "3261"

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Microsoft.Extensions.Logging

type SongMatchingService(spotifyClient: ISpotifyClientService, logger: ILogger<SongMatchingService>) =
    interface ISongMatchingService with
        member _.FindSpotifyMatchAsync
            (
                accessToken: string,
                artist: string,
                title: string,
                album: string | null,
                cancellationToken: CancellationToken
            ) : Task<SpotifyTrack | null> =
            task {
                let strategies =
                    SearchStrategies.getSearchStrategies artist title (Option.ofObj album)

                let mutable found: SpotifyTrack | null = null

                for (query, strategyName) in strategies do
                    if isNull found && not (String.IsNullOrWhiteSpace query) then
                        try
                            let! result =
                                spotifyClient.SearchTrackAsync(accessToken, query, cancellationToken)

                            if not (isNull result) then
                                logger.LogDebug(
                                    "Found match for '{Artist} - {Title}' using strategy '{Strategy}'",
                                    artist,
                                    title,
                                    strategyName
                                )

                                found <- result
                        with ex ->
                            logger.LogWarning(ex, "Search failed for query '{Query}'", query)

                if isNull found then
                    logger.LogDebug("No Spotify match found for '{Artist} - {Title}'", artist, title)

                return found
            }

        member this.MatchSongsToSpotifyAsync
            (
                accessToken: string,
                songs: IEnumerable<Song>,
                progress: IProgress<int> | null,
                cancellationToken: CancellationToken
            ) : Task<IReadOnlyList<MatchResult>> =
            task {
                let songList = songs |> Seq.toList
                let results = List<MatchResult>()
                let mutable processed = 0

                for song in songList do
                    cancellationToken.ThrowIfCancellationRequested()

                    let! matchResult =
                        (this :> ISongMatchingService)
                            .FindSpotifyMatchAsync(accessToken, song.Artist, song.Title, song.Album, cancellationToken)

                    let strategy: string | null =
                        if not (isNull matchResult) then "found" else null

                    results.Add(MatchResult(song, matchResult, strategy))
                    processed <- processed + 1

                    if not (isNull progress) then
                        progress.Report(processed)

                return results :> IReadOnlyList<MatchResult>
            }
