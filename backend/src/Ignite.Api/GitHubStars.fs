namespace Ignite.Api

open System
open System.Net.Http
open System.Text.Json
open System.Threading
open System.Threading.Tasks
open Microsoft.Extensions.Logging

module GitHubStars =
    let repositoryApiUrl =
        "https://api.github.com/repos/scowalt/ignite-for-spotify-app"

    let refreshInterval = TimeSpan.FromHours 1.0
    let retryInterval = TimeSpan.FromMinutes 5.0

    let fetchFromGitHub (client: HttpClient) (ct: CancellationToken) : Task<int option> =
        task {
            use request = new HttpRequestMessage(HttpMethod.Get, repositoryApiUrl)
            request.Headers.Accept.ParseAdd("application/vnd.github+json")
            request.Headers.UserAgent.ParseAdd("ignite-for-spotify")

            use! response = client.SendAsync(request, ct)

            if not response.IsSuccessStatusCode then
                return None
            else
                use! stream = response.Content.ReadAsStreamAsync(ct)
                use! document = JsonDocument.ParseAsync(stream, cancellationToken = ct)

                match document.RootElement.TryGetProperty("stargazers_count") with
                | true, value when value.ValueKind = JsonValueKind.Number ->
                    match value.TryGetInt32() with
                    | true, count when count >= 0 -> return Some count
                    | _ -> return None
                | _ -> return None
        }

type private Snapshot =
    { Stars: int option
      RefreshAfter: DateTimeOffset }

type GitHubStarsCache
    (
        fetch: CancellationToken -> Task<int option>,
        clock: TimeProvider,
        logger: ILogger
    ) =
    let gate = new SemaphoreSlim(1, 1)

    [<VolatileField>]
    let mutable snapshot =
        { Stars = None
          RefreshAfter = DateTimeOffset.MinValue }

    member _.GetAsync(ct: CancellationToken) : Task<int option> =
        task {
            let current = snapshot

            if clock.GetUtcNow() < current.RefreshAfter then
                return current.Stars
            else
                do! gate.WaitAsync(ct)

                try
                    let latest = snapshot
                    let now = clock.GetUtcNow()

                    if now < latest.RefreshAfter then
                        return latest.Stars
                    else
                        try
                            let! fetched = fetch ct

                            match fetched with
                            | Some count ->
                                snapshot <-
                                    { Stars = Some count
                                      RefreshAfter = now + GitHubStars.refreshInterval }
                            | None ->
                                logger.LogWarning("GitHub did not return a usable star count")

                                snapshot <-
                                    { latest with
                                        RefreshAfter = now + GitHubStars.retryInterval }
                        with ex when not ct.IsCancellationRequested ->
                            logger.LogWarning(ex, "Failed to refresh the GitHub star count")

                            snapshot <-
                                { latest with
                                    RefreshAfter = now + GitHubStars.retryInterval }

                        return snapshot.Stars
                finally
                    gate.Release() |> ignore
        }
