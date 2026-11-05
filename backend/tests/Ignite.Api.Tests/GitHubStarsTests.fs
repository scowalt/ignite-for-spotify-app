module Ignite.Api.Tests.GitHubStarsTests

open System
open System.Net
open System.Net.Http
open System.Threading
open System.Threading.Tasks
open Ignite.Api
open Microsoft.Extensions.Logging.Abstractions
open Xunit

type private ManualClock(start: DateTimeOffset) =
    inherit TimeProvider()
    let mutable now = start
    override _.GetUtcNow() = now
    member _.Advance(span: TimeSpan) = now <- now + span

type private StubHandler(respond: HttpRequestMessage -> HttpResponseMessage) =
    inherit HttpMessageHandler()
    member val Requests = ResizeArray<HttpRequestMessage>()

    override this.SendAsync(request, _) =
        this.Requests.Add request
        Task.FromResult(respond request)

let private cacheWith (clock: TimeProvider) (results: (unit -> int option) list) =
    let mutable remaining = results
    let mutable calls = 0

    let fetch (_: CancellationToken) =
        calls <- calls + 1

        match remaining with
        | next :: rest ->
            remaining <- rest
            Task.FromResult(next ())
        | [] -> Task.FromResult None

    GitHubStarsCache(fetch, clock, NullLogger.Instance), (fun () -> calls)

let private start = DateTimeOffset(2026, 11, 5, 12, 0, 0, TimeSpan.Zero)

[<Fact>]
let ``count is fetched once and served from cache within the refresh interval`` () =
    task {
        let clock = ManualClock(start)
        let cache, calls = cacheWith clock [ (fun () -> Some 7); (fun () -> Some 99) ]

        let! first = cache.GetAsync CancellationToken.None
        clock.Advance(TimeSpan.FromMinutes 59.0)
        let! second = cache.GetAsync CancellationToken.None

        Assert.Equal(Some 7, first)
        Assert.Equal(Some 7, second)
        Assert.Equal(1, calls ())
    }

[<Fact>]
let ``count is refreshed after the refresh interval`` () =
    task {
        let clock = ManualClock(start)
        let cache, calls = cacheWith clock [ (fun () -> Some 7); (fun () -> Some 8) ]

        let! _ = cache.GetAsync CancellationToken.None
        clock.Advance(GitHubStars.refreshInterval + TimeSpan.FromSeconds 1.0)
        let! refreshed = cache.GetAsync CancellationToken.None

        Assert.Equal(Some 8, refreshed)
        Assert.Equal(2, calls ())
    }

[<Fact>]
let ``count is unknown when the first fetch fails and retried after the retry interval`` () =
    task {
        let clock = ManualClock(start)
        let cache, calls = cacheWith clock [ (fun () -> None); (fun () -> Some 3) ]

        let! first = cache.GetAsync CancellationToken.None
        clock.Advance(TimeSpan.FromMinutes 1.0)
        let! stillUnknown = cache.GetAsync CancellationToken.None
        clock.Advance(GitHubStars.retryInterval)
        let! recovered = cache.GetAsync CancellationToken.None

        Assert.Equal(None, first)
        Assert.Equal(None, stillUnknown)
        Assert.Equal(Some 3, recovered)
        Assert.Equal(2, calls ())
    }

[<Fact>]
let ``last known count survives a failed refresh`` () =
    task {
        let clock = ManualClock(start)

        let cache, _ =
            cacheWith clock [ (fun () -> Some 12); (fun () -> failwith "GitHub is down") ]

        let! _ = cache.GetAsync CancellationToken.None
        clock.Advance(GitHubStars.refreshInterval + TimeSpan.FromSeconds 1.0)
        let! afterFailure = cache.GetAsync CancellationToken.None

        Assert.Equal(Some 12, afterFailure)
    }

[<Fact>]
let ``caller cancellation is not swallowed`` () =
    task {
        use cancellation = new CancellationTokenSource()
        cancellation.Cancel()

        let cache =
            GitHubStarsCache(
                (fun ct -> Task.FromCanceled<int option>(ct)),
                TimeProvider.System,
                NullLogger.Instance
            )

        let! caught =
            Assert.ThrowsAnyAsync<OperationCanceledException>(fun () ->
                cache.GetAsync cancellation.Token :> Task)

        Assert.NotNull caught
    }

let private fetchWith (response: HttpResponseMessage) =
    task {
        use handler = new StubHandler(fun _ -> response)
        use client = new HttpClient(handler, disposeHandler = false)
        let! count = GitHubStars.fetchFromGitHub client CancellationToken.None
        return count, handler.Requests
    }

[<Fact>]
let ``stargazers_count is read from the GitHub repository response`` () =
    task {
        let body = new StringContent("""{"id":1,"stargazers_count":23250}""")
        let! count, requests = fetchWith (new HttpResponseMessage(HttpStatusCode.OK, Content = body))

        Assert.Equal(Some 23250, count)
        let request = Assert.Single requests
        Assert.Equal(GitHubStars.repositoryApiUrl, request.RequestUri.ToString())
        Assert.NotEmpty request.Headers.UserAgent
    }

[<Fact>]
let ``error responses and malformed bodies yield no count`` () =
    task {
        let! forbidden, _ = fetchWith (new HttpResponseMessage(HttpStatusCode.Forbidden))

        let! missing, _ =
            fetchWith (new HttpResponseMessage(HttpStatusCode.OK, Content = new StringContent("{}")))

        let! wrongType, _ =
            fetchWith (
                new HttpResponseMessage(
                    HttpStatusCode.OK,
                    Content = new StringContent("""{"stargazers_count":"many"}""")
                )
            )

        Assert.Equal(None, forbidden)
        Assert.Equal(None, missing)
        Assert.Equal(None, wrongType)
    }
