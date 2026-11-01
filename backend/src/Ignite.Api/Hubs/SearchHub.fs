namespace Ignite.Api.Hubs

open System
open System.Collections.Generic
open System.Threading.Tasks
open Microsoft.AspNetCore.SignalR
open Microsoft.Extensions.Logging

type SearchProgressUpdate(sessionId: string, processed: int, total: int, currentItem: string) =
    member _.SessionId = sessionId
    member _.Processed = processed
    member _.Total = total
    member _.CurrentItem = currentItem

type SpotifyTrackInfo(id: string, name: string, artists: string array, album: string) =
    member _.Id = id
    member _.Name = name
    member _.Artists = artists
    member _.Album = album

type CdlcMatchInfo
    (
        id: int,
        artist: string,
        title: string,
        album: string,
        author: string | null,
        lead: bool,
        rhythm: bool,
        bass: bool,
        vocals: bool,
        officialDlc: bool,
        downloadLink: string
    ) =
    member _.Id = id
    member _.Artist = artist
    member _.Title = title
    member _.Album = album
    member _.Author = author
    member _.Lead = lead
    member _.Rhythm = rhythm
    member _.Bass = bass
    member _.Vocals = vocals
    member _.OfficialDlc = officialDlc
    member _.DownloadLink = downloadLink

type SearchResultUpdate
    (sessionId: string, spotifyTrack: SpotifyTrackInfo, matches: IEnumerable<CdlcMatchInfo>, matchCount: int) =
    member _.SessionId = sessionId
    member _.SpotifyTrack = spotifyTrack
    member _.Matches = matches
    member _.MatchCount = matchCount

type PlaylistSearchResult(spotifyTrack: SpotifyTrackInfo, matches: IEnumerable<CdlcMatchInfo>) =
    member _.SpotifyTrack = spotifyTrack
    member _.Matches = matches

type SearchCompleteUpdate
    (
        sessionId: string,
        totalTracks: int,
        processedTracks: int,
        matchedTracks: int,
        totalMatches: int,
        skippedTracks: int,
        failedTracks: int,
        unprocessedTracks: int,
        isComplete: bool,
        failureReason: string | null,
        duration: TimeSpan
    ) =
    member _.SessionId = sessionId
    member _.TotalTracks = totalTracks
    member _.ProcessedTracks = processedTracks
    member _.MatchedTracks = matchedTracks
    member _.TotalMatches = totalMatches
    member _.SkippedTracks = skippedTracks
    member _.FailedTracks = failedTracks
    member _.UnprocessedTracks = unprocessedTracks
    member _.IsComplete = isComplete
    member _.FailureReason = failureReason
    member _.Duration = duration

type JobProgressUpdate
    (jobId: string, jobType: string, processed: int, total: int, added: int, updated: int, status: string) =
    member _.JobId = jobId
    member _.JobType = jobType
    member _.Processed = processed
    member _.Total = total
    member _.Added = added
    member _.Updated = updated
    member _.Status = status

type JobCompleteUpdate
    (
        jobId: string,
        jobType: string,
        status: string,
        totalProcessed: int,
        added: int,
        updated: int,
        errorMessage: string | null,
        duration: TimeSpan
    ) =
    member _.JobId = jobId
    member _.JobType = jobType
    member _.Status = status
    member _.TotalProcessed = totalProcessed
    member _.Added = added
    member _.Updated = updated
    member _.ErrorMessage = errorMessage
    member _.Duration = duration

type ErrorUpdate(sessionId: string, message: string, details: string | null) =
    member _.SessionId = sessionId
    member _.Message = message
    member _.Details = details

type ISearchHubClient =
    abstract ReceiveSearchProgress: update: SearchProgressUpdate -> Task
    abstract ReceiveSearchResult: result: SearchResultUpdate -> Task
    abstract ReceiveSearchComplete: complete: SearchCompleteUpdate -> Task
    abstract ReceiveJobProgress: update: JobProgressUpdate -> Task
    abstract ReceiveJobComplete: complete: JobCompleteUpdate -> Task
    abstract ReceiveError: error: ErrorUpdate -> Task

type SearchHub(logger: ILogger<SearchHub>) =
    inherit Hub<ISearchHubClient>()

    override this.OnConnectedAsync() =
        logger.LogInformation("Client connected: {ConnectionId}", this.Context.ConnectionId)
        base.OnConnectedAsync()

    override this.OnDisconnectedAsync(``exception``: Exception | null) =
        logger.LogInformation("Client disconnected: {ConnectionId}", this.Context.ConnectionId)
        base.OnDisconnectedAsync(``exception``)

    member this.JoinSearchSession(sessionId: string) =
        task {
            do! this.Groups.AddToGroupAsync(this.Context.ConnectionId, $"search_{sessionId}")
            logger.LogDebug("Client {ConnectionId} joined search session {SessionId}", this.Context.ConnectionId, sessionId)
        }
        :> Task

    member this.LeaveSearchSession(sessionId: string) =
        task {
            do! this.Groups.RemoveFromGroupAsync(this.Context.ConnectionId, $"search_{sessionId}")
            logger.LogDebug("Client {ConnectionId} left search session {SessionId}", this.Context.ConnectionId, sessionId)
        }
        :> Task

    member this.JoinJobUpdates(jobId: string) =
        task {
            do! this.Groups.AddToGroupAsync(this.Context.ConnectionId, $"job_{jobId}")
            logger.LogDebug("Client {ConnectionId} joined job updates for {JobId}", this.Context.ConnectionId, jobId)
        }
        :> Task

    member this.LeaveJobUpdates(jobId: string) =
        task {
            do! this.Groups.RemoveFromGroupAsync(this.Context.ConnectionId, $"job_{jobId}")
            logger.LogDebug("Client {ConnectionId} left job updates for {JobId}", this.Context.ConnectionId, jobId)
        }
        :> Task
