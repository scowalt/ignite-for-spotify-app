namespace Ignite.Jobs.Jobs

#nowarn "3261"

open System
open System.Collections.Generic
open System.Runtime.ExceptionServices
open System.Threading
open System.Threading.Tasks
open Hangfire
open Hangfire.Server
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Microsoft.Extensions.Logging

type ScrapeCdlcJob
    (
        scraper: ICdlcScraper,
        songRepository: ISongRepository,
        scrapingJobRepository: IScrapingJobRepository,
        logger: ILogger<ScrapeCdlcJob>
    ) =

    [<Literal>]
    let BatchSize = 25

    member private _.ProcessBatchAsync(batch: List<Song>, cancellationToken: CancellationToken) =
        task {
            try
                return! songRepository.BulkUpsertAsync(batch, cancellationToken)
            with ex ->
                logger.LogError(ex, "Error processing batch of {Count} songs", batch.Count)
                ExceptionDispatchInfo.Capture(ex).Throw()
                return struct (0, 0)
        }

    [<AutomaticRetry(Attempts = 1)>]
    [<DisableConcurrentExecution(timeoutInSeconds = 7200)>]
    [<Queue("scraping")>]
    member this.ExecuteAsync(context: PerformContext | null, cancellationToken: CancellationToken) =
        task {
            let hangfireJobId =
                if not (isNull context) && not (isNull context.BackgroundJob) then
                    context.BackgroundJob.Id
                else
                    Guid.NewGuid().ToString()

            let scrapingJob = ScrapingJob()
            scrapingJob.JobType <- ScrapingJobType.CdlcFull
            scrapingJob.Status <- ScrapingJobStatus.Running
            scrapingJob.HangfireJobId <- hangfireJobId
            scrapingJob.StartedAt <- Nullable(DateTime.UtcNow)

            do! scrapingJobRepository.CreateAsync(scrapingJob, cancellationToken) :> Task

            try
                logger.LogInformation("Starting CDLC scrape job {JobId}", hangfireJobId)

                let mutable processed = 0
                let mutable added = 0
                let mutable updated = 0
                let batch = List<Song>(BatchSize)

                let progress =
                    Progress<struct (int * int)>(fun struct (p, total) ->
                        if p % 100 = 0 || p = total then
                            logger.LogInformation("Scraping progress: {Processed}/{Total}", p, total))

                let enumerator =
                    scraper.ScrapeAllSongsAsync(progress, cancellationToken).GetAsyncEnumerator(cancellationToken)

                let mutable hasMore = true

                while hasMore do
                    let! moveNext = enumerator.MoveNextAsync()
                    hasMore <- moveNext

                    if hasMore then
                        batch.Add(enumerator.Current)

                        if batch.Count >= BatchSize then
                            let! struct (batchAdded, batchUpdated) =
                                this.ProcessBatchAsync(batch, cancellationToken)

                            added <- added + batchAdded
                            updated <- updated + batchUpdated
                            processed <- processed + batch.Count
                            batch.Clear()

                            scrapingJob.SongsProcessed <- processed
                            scrapingJob.SongsAdded <- added
                            scrapingJob.SongsUpdated <- updated
                            do! scrapingJobRepository.UpdateAsync(scrapingJob, cancellationToken) :> Task

                do! enumerator.DisposeAsync().AsTask()

                if batch.Count > 0 then
                    let! struct (batchAdded, batchUpdated) = this.ProcessBatchAsync(batch, cancellationToken)
                    added <- added + batchAdded
                    updated <- updated + batchUpdated
                    processed <- processed + batch.Count

                scrapingJob.Status <- ScrapingJobStatus.Completed
                scrapingJob.SongsProcessed <- processed
                scrapingJob.SongsAdded <- added
                scrapingJob.SongsUpdated <- updated
                scrapingJob.CompletedAt <- Nullable(DateTime.UtcNow)
                do! scrapingJobRepository.UpdateAsync(scrapingJob, cancellationToken) :> Task

                logger.LogInformation(
                    "Scraping job {JobId} completed: {Processed} processed, {Added} added, {Updated} updated",
                    hangfireJobId,
                    processed,
                    added,
                    updated
                )
            with
            | :? OperationCanceledException as ex ->
                scrapingJob.Status <- ScrapingJobStatus.Cancelled
                scrapingJob.ErrorMessage <- "Job was cancelled"
                scrapingJob.CompletedAt <- Nullable(DateTime.UtcNow)
                do! scrapingJobRepository.UpdateAsync(scrapingJob, CancellationToken.None) :> Task
                ExceptionDispatchInfo.Capture(ex).Throw()
            | ex ->
                logger.LogError(ex, "Scraping job {JobId} failed", hangfireJobId)
                scrapingJob.Status <- ScrapingJobStatus.Failed
                scrapingJob.ErrorMessage <- ex.Message
                scrapingJob.CompletedAt <- Nullable(DateTime.UtcNow)
                do! scrapingJobRepository.UpdateAsync(scrapingJob, CancellationToken.None) :> Task
                ExceptionDispatchInfo.Capture(ex).Throw()
        }
        :> Task

type UpdateSpotifyIdsJob
    (
        songRepository: ISongRepository,
        sessionRepository: IUserSessionRepository,
        matchingService: ISongMatchingService,
        logger: ILogger<UpdateSpotifyIdsJob>
    ) =

    [<Literal>]
    let BatchSize = 100

    [<AutomaticRetry(Attempts = 3)>]
    [<Queue("matching")>]
    member _.ExecuteAsync
        (
            sessionId: string,
            maxSongs: int,
            context: PerformContext | null,
            cancellationToken: CancellationToken
        ) =
        task {
            let jobId =
                if not (isNull context) && not (isNull context.BackgroundJob) then
                    context.BackgroundJob.Id
                else
                    Guid.NewGuid().ToString()

            logger.LogInformation(
                "Starting Spotify ID update job {JobId} for up to {MaxSongs} songs",
                jobId,
                maxSongs
            )

            let! session = sessionRepository.GetByIdAsync(sessionId, cancellationToken)

            if isNull session || String.IsNullOrEmpty(session.SpotifyAccessToken) then
                logger.LogError("Session {SessionId} not found or has no access token", sessionId)
                raise (InvalidOperationException($"Session {sessionId} not found or has no access token"))

            let accessToken = session.SpotifyAccessToken
            let mutable processed = 0
            let mutable matched = 0
            let mutable failed = 0
            let mutable keepGoing = true

            while keepGoing && processed < maxSongs do
                cancellationToken.ThrowIfCancellationRequested()

                let! songs = songRepository.GetSongsWithoutSpotifyIdAsync(BatchSize, cancellationToken)

                if songs.Count = 0 then
                    logger.LogInformation("No more songs without Spotify IDs")
                    keepGoing <- false
                else
                    let mutable i = 0

                    while i < songs.Count && processed < maxSongs do
                        cancellationToken.ThrowIfCancellationRequested()
                        let song = songs.[i]

                        try
                            let! matchResult =
                                matchingService.FindSpotifyMatchAsync(
                                    accessToken,
                                    song.Artist,
                                    song.Title,
                                    song.Album,
                                    cancellationToken
                                )

                            if not (isNull matchResult) then
                                song.SpotifyTrackId <- matchResult.Id
                                do! songRepository.UpdateAsync(song, cancellationToken) :> Task
                                matched <- matched + 1

                                logger.LogDebug(
                                    "Matched '{Artist} - {Title}' to Spotify track {TrackId}",
                                    song.Artist,
                                    song.Title,
                                    matchResult.Id
                                )
                        with ex ->
                            logger.LogWarning(ex, "Failed to match '{Artist} - {Title}'", song.Artist, song.Title)
                            failed <- failed + 1

                        processed <- processed + 1
                        i <- i + 1

                        if processed % 100 = 0 then
                            logger.LogInformation(
                                "Spotify matching progress: {Processed} processed, {Matched} matched, {Failed} failed",
                                processed,
                                matched,
                                failed
                            )

            logger.LogInformation(
                "Spotify ID update job {JobId} completed: {Processed} processed, {Matched} matched, {Failed} failed",
                jobId,
                processed,
                matched,
                failed
            )
        }
        :> Task
