namespace Ignite.Api.Hubs

open System.Collections.Generic
open System.Linq
open System.Threading.Tasks
open Microsoft.AspNetCore.SignalR
open Microsoft.Extensions.Logging

type IHubNotificationService =
    abstract SendSearchProgressAsync: sessionId: string * processed: int * total: int * currentItem: string -> Task
    abstract SendSearchResultAsync: sessionId: string * track: SpotifyTrackInfo * matches: IEnumerable<CdlcMatchInfo> -> Task
    abstract SendSearchCompleteAsync: sessionId: string * totalTracks: int * processedTracks: int * matchedTracks: int * totalMatches: int * skippedTracks: int * failedTracks: int * unprocessedTracks: int * isComplete: bool * failureReason: string | null * duration: System.TimeSpan -> Task
    abstract SendJobProgressAsync: jobId: string * jobType: string * processed: int * total: int * added: int * updated: int * status: string -> Task
    abstract SendJobCompleteAsync: jobId: string * jobType: string * status: string * totalProcessed: int * added: int * updated: int * errorMessage: string | null * duration: System.TimeSpan -> Task
    abstract SendErrorAsync: sessionId: string * message: string * ?details: string -> Task

type HubNotificationService(hubContext: IHubContext<SearchHub, ISearchHubClient>, logger: ILogger<HubNotificationService>) =

    interface IHubNotificationService with
        member _.SendSearchProgressAsync(sessionId, processed, total, currentItem) =
            let update = SearchProgressUpdate(sessionId, processed, total, currentItem)
            hubContext.Clients.Group($"search_{sessionId}").ReceiveSearchProgress(update)

        member _.SendSearchResultAsync(sessionId, track, matches) =
            let matchList = matches.ToList()
            let update = SearchResultUpdate(sessionId, track, matchList, matchList.Count)
            hubContext.Clients.Group($"search_{sessionId}").ReceiveSearchResult(update)

        member _.SendSearchCompleteAsync(sessionId, totalTracks, processedTracks, matchedTracks, totalMatches, skippedTracks, failedTracks, unprocessedTracks, isComplete, failureReason, duration) =
            let update =
                SearchCompleteUpdate(
                    sessionId,
                    totalTracks,
                    processedTracks,
                    matchedTracks,
                    totalMatches,
                    skippedTracks,
                    failedTracks,
                    unprocessedTracks,
                    isComplete,
                    failureReason,
                    duration
                )

            hubContext.Clients.Group($"search_{sessionId}").ReceiveSearchComplete(update)

        member _.SendJobProgressAsync(jobId, jobType, processed, total, added, updated, status) =
            task {
                let update = JobProgressUpdate(jobId, jobType, processed, total, added, updated, status)
                do! hubContext.Clients.Group($"job_{jobId}").ReceiveJobProgress(update)
                do! hubContext.Clients.All.ReceiveJobProgress(update)
            }
            :> Task

        member _.SendJobCompleteAsync(jobId, jobType, status, totalProcessed, added, updated, errorMessage, duration) =
            task {
                let update = JobCompleteUpdate(jobId, jobType, status, totalProcessed, added, updated, errorMessage, duration)
                do! hubContext.Clients.Group($"job_{jobId}").ReceiveJobComplete(update)
                do! hubContext.Clients.All.ReceiveJobComplete(update)
            }
            :> Task

        member _.SendErrorAsync(sessionId, message, ?details) =
            let detailsValue = defaultArg details null
            let update = ErrorUpdate(sessionId, message, detailsValue)
            hubContext.Clients.Group($"search_{sessionId}").ReceiveError(update)
