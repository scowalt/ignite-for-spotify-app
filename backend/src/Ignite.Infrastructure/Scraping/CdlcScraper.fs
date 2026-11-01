namespace Ignite.Infrastructure.Scraping

open System
open System.Collections.Generic
open System.Net.Http
open System.Text
open System.Text.Json
open System.Text.Json.Serialization
open System.Text.RegularExpressions
open System.Threading
open System.Threading.Tasks
open System.Threading.RateLimiting
open System.Web
open FSharp.Control
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Microsoft.Extensions.Logging
open Microsoft.Extensions.Options
open Polly
open Polly.RateLimiting
open Polly.Retry

[<CLIMutable>]
type LivewireCall =
    { [<JsonPropertyName("path")>]
      Path: string
      [<JsonPropertyName("method")>]
      Method: string
      [<JsonPropertyName("params")>]
      Params: List<obj> }

[<CLIMutable>]
type LivewireComponent =
    { [<JsonPropertyName("calls")>]
      Calls: List<LivewireCall>
      [<JsonPropertyName("snapshot")>]
      Snapshot: string
      [<JsonPropertyName("updates")>]
      Updates: Dictionary<string, obj> }

[<CLIMutable>]
type LivewireRequest =
    { [<JsonPropertyName("components")>]
      Components: List<LivewireComponent> }

type CdlcScraper
    (
        httpClient: HttpClient,
        config: IOptions<CdlcScraperConfig>,
        logger: ILogger<CdlcScraper>,
        cookiePersistence: CookiePersistence
    ) =

    let config = config.Value
    let mutable csrfToken: string | null = null
    let mutable currentSnapshot: string | null = null
    let mutable livewireEndpoint: string | null = null

    let hasCredentials =
        not (String.IsNullOrEmpty(config.Username))
        && not (String.IsNullOrEmpty(config.Password))

    let pipeline =
        let rateLimiter =
            new SlidingWindowRateLimiter(
                SlidingWindowRateLimiterOptions(
                    PermitLimit = config.MaxRequestsPerSecond,
                    Window = TimeSpan.FromSeconds(1.0),
                    SegmentsPerWindow = 1,
                    QueueProcessingOrder = QueueProcessingOrder.OldestFirst,
                    QueueLimit = config.QueueLimit
                )
            )

        ResiliencePipelineBuilder()
            .AddRateLimiter(
                RateLimiterStrategyOptions(
                    RateLimiter = fun args -> rateLimiter.AcquireAsync(1, args.Context.CancellationToken)
                )
            )
            .AddRetry(
                RetryStrategyOptions(
                    MaxRetryAttempts = config.MaxRetryAttempts,
                    Delay = TimeSpan.FromSeconds(1.0),
                    BackoffType = DelayBackoffType.Exponential,
                    ShouldHandle = PredicateBuilder().Handle<HttpRequestException>(),
                    OnRetry =
                        fun args ->
                            logger.LogWarning(
                                "Request to Ignition4 failed, retrying in {Delay}ms (attempt {Attempt}/{Max})",
                                args.RetryDelay.TotalMilliseconds,
                                args.AttemptNumber,
                                config.MaxRetryAttempts
                            )

                            ValueTask.CompletedTask
                )
            )
            .Build()

    do
        httpClient.DefaultRequestHeaders.Clear()

        httpClient.DefaultRequestHeaders.Add(
            "User-Agent",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        httpClient.DefaultRequestHeaders.Add("Accept", "text/html, application/xhtml+xml, application/json")

        if hasCredentials then
            logger.LogInformation("CDLC scraper configured with username/password authentication")
        elif not (String.IsNullOrEmpty(config.Cookies)) then
            httpClient.DefaultRequestHeaders.Add("Cookie", config.Cookies)
            logger.LogInformation("CDLC scraper configured with static cookies (legacy)")
        else
            logger.LogWarning("CDLC scraper running without authentication - some content may not be accessible")

    member private this.EnsureAuthenticatedAsync(cancellationToken: CancellationToken) =
        task {
            use cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken)
            cts.CancelAfter(TimeSpan.FromSeconds(30.0))
            let! homepageHtml = httpClient.GetStringAsync(config.BaseUrl, cts.Token)
            let csrfTokenMatch = Regex.Match(homepageHtml, @"csrf-token""\s*content=""([^""]+)""")

            let sessionValid =
                csrfTokenMatch.Success
                && homepageHtml.Contains("logout", StringComparison.OrdinalIgnoreCase)
                && not (homepageHtml.Contains("data-guest-cta"))

            if sessionValid then
                csrfToken <- csrfTokenMatch.Groups.[1].Value
                logger.LogInformation("Existing ignition4 session is still valid, skipping login")
            else
                if not hasCredentials then
                    raise (
                        InvalidOperationException(
                            "No valid ignition4 session and no credentials configured. "
                            + "Set CDLC_SCRAPER_USERNAME and CDLC_SCRAPER_PASSWORD."
                        )
                    )

                logger.LogInformation("Session expired or missing, logging into CustomsForge...")
                do! this.LoginAsync(cancellationToken)

                let! homepageHtml = httpClient.GetStringAsync(config.BaseUrl, cancellationToken)
                let csrfTokenMatch = Regex.Match(homepageHtml, @"csrf-token""\s*content=""([^""]+)""")

                if not csrfTokenMatch.Success then
                    raise (
                        InvalidOperationException("Failed to extract CSRF token from Ignition4 after authentication")
                    )

                csrfToken <- csrfTokenMatch.Groups.[1].Value
        }

    member private this.LoginAsync(cancellationToken: CancellationToken) =
        task {
            let! oauthResponse = httpClient.GetAsync($"{config.BaseUrl}/login", cancellationToken)

            let finalUrl =
                if isNull oauthResponse.RequestMessage || isNull oauthResponse.RequestMessage.RequestUri then
                    ""
                else
                    oauthResponse.RequestMessage.RequestUri.ToString()

            if finalUrl.Contains("ignition4.customsforge.com") then
                logger.LogInformation(
                    "OAuth auto-approved via existing customsforge.com session (no re-login needed)"
                )

                cookiePersistence.Save()
            else
                let! oauthPageHtml = oauthResponse.Content.ReadAsStringAsync(cancellationToken)
                let csrfKeyMatch = Regex.Match(oauthPageHtml, @"name=""csrfKey"" value=""([^""]+)""")

                if not csrfKeyMatch.Success then
                    raise (
                        InvalidOperationException(
                            "Failed to extract csrfKey from CustomsForge OAuth login page. "
                            + "The page may have changed or the OAuth flow is broken."
                        )
                    )

                let csrfKey = csrfKeyMatch.Groups.[1].Value

                let loginContent =
                    new FormUrlEncodedContent(
                        dict
                            [ "auth", config.Username
                              "password", config.Password
                              "_processLogin", "usernamepassword"
                              "csrfKey", csrfKey
                              "remember_me", "1" ]
                    )

                do!
                    httpClient.PostAsync("https://customsforge.com/oauth/authorize/", loginContent, cancellationToken)
                    :> Task

                logger.LogInformation("CustomsForge login submitted, completing OAuth flow...")
                do! httpClient.GetAsync($"{config.BaseUrl}/login", cancellationToken) :> Task
                logger.LogInformation("Successfully authenticated with ignition4")
                cookiePersistence.Save()
                logger.LogDebug("Persisted cookies to disk")
        }

    member private this.InitializeSessionAsync(cancellationToken: CancellationToken) =
        task {
            do! this.EnsureAuthenticatedAsync(cancellationToken)

            let searchUrl = $"{config.BaseUrl}{config.SearchPath}"

            let! html =
                pipeline.ExecuteAsync(
                    (fun (ct: CancellationToken) ->
                        ValueTask<string>(
                            task {
                                let! response = httpClient.GetAsync(searchUrl, ct)
                                response.EnsureSuccessStatusCode() |> ignore

                                let requestedPath = Uri(searchUrl).AbsolutePath

                                if
                                    not (isNull response.RequestMessage)
                                    && not (isNull response.RequestMessage.RequestUri)
                                    && not (
                                        String.Equals(
                                            response.RequestMessage.RequestUri.AbsolutePath.TrimEnd('/'),
                                            requestedPath.TrimEnd('/'),
                                            StringComparison.OrdinalIgnoreCase
                                        )
                                    )
                                then
                                    raise (
                                        HttpRequestException(
                                            $"Ignition4 advanced search request redirected from {requestedPath} to {response.RequestMessage.RequestUri.AbsolutePath}"
                                        )
                                    )

                                return! response.Content.ReadAsStringAsync(ct)
                            }
                        )),
                    cancellationToken
                )

            let csrfMatch = Regex.Match(html, @"csrf-token""\s*content=""([^""]+)""")

            if csrfMatch.Success then
                csrfToken <- csrfMatch.Groups.[1].Value

            let uriMatch = Regex.Match(html, @"""uri""\s*:\s*""([^""]+)""")

            livewireEndpoint <-
                if uriMatch.Success then
                    let endpoint = uriMatch.Groups.[1].Value.Replace("\\/", "/")

                    if endpoint.StartsWith("http", StringComparison.OrdinalIgnoreCase) then
                        endpoint
                    elif endpoint.StartsWith("/") then
                        $"{config.BaseUrl}{endpoint}"
                    else
                        $"{config.BaseUrl}/{endpoint}"
                else
                    $"{config.BaseUrl}{config.LivewirePath}"

            currentSnapshot <- null

            let snapshotPattern = @"wire:snapshot\s*=\s*(?:""([^""]*)""|'([^']*)')"

            for snapshotMatch in Regex.Matches(html, snapshotPattern, RegexOptions.IgnoreCase) do
                let encodedSnapshot =
                    if snapshotMatch.Groups.[1].Success then
                        snapshotMatch.Groups.[1].Value
                    else
                        snapshotMatch.Groups.[2].Value

                let decodedSnapshot = HttpUtility.HtmlDecode(encodedSnapshot)

                try
                    use document = JsonDocument.Parse(decodedSnapshot)
                    let mutable memo = Unchecked.defaultof<JsonElement>
                    let mutable name = Unchecked.defaultof<JsonElement>

                    if
                        document.RootElement.ValueKind = JsonValueKind.Object
                        && document.RootElement.TryGetProperty("memo", &memo)
                        && memo.ValueKind = JsonValueKind.Object
                        && memo.TryGetProperty("name", &name)
                        && name.ValueKind = JsonValueKind.String
                        && name.GetString() = "advanced-search"
                    then
                        currentSnapshot <- decodedSnapshot
                with :? JsonException -> ()

            if String.IsNullOrEmpty(currentSnapshot) then
                raise (InvalidOperationException("Failed to extract advanced-search snapshot from Ignition4"))
        }

    member private _.SendLivewireRequestAsync
        (
            payload: LivewireRequest,
            cancellationToken: CancellationToken
        ) =
        pipeline.ExecuteAsync(
            (fun (ct: CancellationToken) ->
                ValueTask<struct (string * string)>(
                    task {
                        let endpoint =
                            if String.IsNullOrEmpty(livewireEndpoint) then
                                $"{config.BaseUrl}{config.LivewirePath}"
                            else
                                livewireEndpoint

                        let json = JsonSerializer.Serialize(payload)
                        use content = new StringContent(json, Encoding.UTF8, "application/json")
                        use request = new HttpRequestMessage(HttpMethod.Post, endpoint)
                        request.Content <- content
                        request.Headers.Add("X-CSRF-TOKEN", csrfToken)
                        request.Headers.Add("X-Livewire", "true")

                        use! response = httpClient.SendAsync(request, ct)
                        response.EnsureSuccessStatusCode() |> ignore
                        let! responseJson = response.Content.ReadAsStringAsync(ct)
                        use document = JsonDocument.Parse(responseJson)
                        let components = document.RootElement.GetProperty("components")

                        if components.ValueKind <> JsonValueKind.Array || components.GetArrayLength() = 0 then
                            raise (InvalidOperationException("Invalid Livewire response"))

                        let responseComponent = components.[0]

                        let html =
                            responseComponent.GetProperty("effects").GetProperty("html").GetString()

                        let snapshot =
                            let value = responseComponent.GetProperty("snapshot").GetString()

                            if String.IsNullOrEmpty(value) then
                                currentSnapshot
                            else
                                value

                        return struct (html, snapshot)
                    }
                )),
            cancellationToken
        )

    member private this.FetchFirstPageAsync(cancellationToken: CancellationToken) =
        task {
            let updates = Dictionary<string, obj>()
            updates.Add("query", box "*")
            updates.Add("perPage", box config.PageSize)
            updates.Add("sortBy", box "added")
            updates.Add("sortDirection", box "desc")

            let requestComponent =
                { Calls = List<LivewireCall>()
                  Snapshot = currentSnapshot
                  Updates = updates }

            let payload =
                { Components = List<LivewireComponent>([ requestComponent ]) }

            let! struct (html, snapshot) =
                this.SendLivewireRequestAsync(payload, cancellationToken)

            currentSnapshot <- snapshot
            return struct (this.ParseSongsFromHtml(html), CdlcScraper.ExtractMaxPage(html))
        }

    member private this.FetchPageAsync(page: int, cancellationToken: CancellationToken) =
        task {
            let parameters = List<obj>()
            parameters.Add(box page)
            parameters.Add(box "page")

            let call =
                { Path = ""
                  Method = "gotoPage"
                  Params = parameters }

            let requestComponent =
                { Calls = List<LivewireCall>([ call ])
                  Snapshot = currentSnapshot
                  Updates = Dictionary<string, obj>() }

            let payload =
                { Components = List<LivewireComponent>([ requestComponent ]) }

            let! struct (html, snapshot) =
                this.SendLivewireRequestAsync(payload, cancellationToken)

            currentSnapshot <- snapshot
            return this.ParseSongsFromHtml(html)
        }

    member private this.ParseSongsFromHtml(html: string) =
        let songs = List<Song>()

        let cardPattern =
            @"<div class=""bg-neutral-900/80 border border-gray-700/70 rounded-lg shadow-lg overflow-hidden"

        let segments = Regex.Split(html, cardPattern) |> Array.ofSeq

        let isOfficial (cardIndex: int) =
            if cardIndex <= 0 then
                false
            else
                let previous: string = segments.[cardIndex - 1]

                let marker = previous.LastIndexOf(CdlcScraper.OfficialDlcClassMarker, StringComparison.Ordinal)
                let previousCardContent = previous.LastIndexOf("</h3>", StringComparison.Ordinal)

                marker >= 0 && marker > previousCardContent

        for index in 1 .. segments.Length - 1 do
            try
                match this.ParseSongCard(segments.[index]) with
                | Some (song: Song) ->
                    song.OfficialDlc <- isOfficial index
                    songs.Add(song)
                | None -> ()
            with ex ->
                logger.LogWarning(ex, "Failed to parse song card")

        songs

    static member private ExtractMaxPage(html: string) =
        let mutable maxPage = 1

        for pageMatch in Regex.Matches(html, @"paginator-page-page(\d+)") do
            match Int32.TryParse(pageMatch.Groups.[1].Value) with
            | true, page when page > maxPage -> maxPage <- page
            | _ -> ()

        maxPage

    static member val OfficialDlcClassMarker: string = "bg-red-500'"

    member private _.ParseSongCard(cardHtml: string) =
        let idMatch = Regex.Match(cardHtml, @"/cdlc/(\d+)")

        if not idMatch.Success then
            None
        else
            let titleMatch = Regex.Match(cardHtml, @"<h3[^>]*>\s*([^<]+)\s*</h3>")

            let artistMatch =
                Regex.Match(cardHtml, @"/artist/\d+""[^>]*>\s*([^<]+)\s*</a>")

            let albumMatch =
                Regex.Match(cardHtml, @"/artist/\d+/album/[^""]*""[^>]*>\s*([^<]+)\s*</a>")

            let authorMatch = Regex.Match(cardHtml, "/profile/([^\"]+)\"")
            let tuningMatch = Regex.Match(cardHtml, "title=\"[^\"]*-\\s*([^\"]+)\"")

            let decode (value: string) = HttpUtility.HtmlDecode(value.Trim())
            let sanitize (value: string) = value.Replace("@", "(at)")

            let title =
                if titleMatch.Success then
                    titleMatch.Groups.[1].Value |> decode |> sanitize
                else
                    "Unknown"

            let artist =
                if artistMatch.Success then
                    artistMatch.Groups.[1].Value |> decode |> sanitize
                else
                    "Unknown"

            let album =
                if albumMatch.Success then
                    albumMatch.Groups.[1].Value |> decode |> sanitize
                else
                    artist

            let author =
                if authorMatch.Success then
                    authorMatch.Groups.[1].Value |> decode |> sanitize
                else
                    "Unknown"

            let tuning =
                if tuningMatch.Success then
                    tuningMatch.Groups.[1].Value |> decode |> sanitize
                else
                    null

            let song = Song()
            song.Artist <- artist
            song.Title <- title
            song.Album <- album
            song.Tuning <- tuning
            song.Author <- author
            song.Lead <- cardHtml.Contains("part-lead")
            song.Rhythm <- cardHtml.Contains("part-rhythm")
            song.Bass <- cardHtml.Contains("part-bass")
            song.Vocals <- cardHtml.Contains("part-vocals")

            song.DynamicDifficulty <-
                cardHtml.Contains("Dynamic Difficulty", StringComparison.OrdinalIgnoreCase)

            song.DownloadLink <- $"https://ignition4.customsforge.com/cdlc/{idMatch.Groups.[1].Value}"
            Some song

    interface ICdlcScraper with
        member this.GetTotalSongCountAsync(cancellationToken: CancellationToken) =
            task {
                do! this.InitializeSessionAsync(cancellationToken)
                let! struct (_, maxPage) = this.FetchFirstPageAsync(cancellationToken)
                return maxPage * config.PageSize
            }

        member this.ScrapeAllSongsAsync
            (
                progress: IProgress<struct (int * int)> | null,
                cancellationToken: CancellationToken
            ) =
            taskSeq {
                do! this.InitializeSessionAsync(cancellationToken)

                let! struct (firstPage, maxPage) = this.FetchFirstPageAsync(cancellationToken)
                let total = maxPage * config.PageSize
                let mutable processed = 0

                logger.LogInformation(
                    "Starting to scrape approximately {Total} songs from Ignition4 via Livewire at {Rate} req/sec",
                    total,
                    config.MaxRequestsPerSecond
                )

                for song in firstPage do
                    processed <- processed + 1

                    if not (isNull progress) then
                        progress.Report(struct (processed, total))

                    yield song

                let mutable pageNumber = 2
                let mutable keepGoing = true

                while keepGoing && pageNumber <= maxPage do
                    cancellationToken.ThrowIfCancellationRequested()
                    let! page = this.FetchPageAsync(pageNumber, cancellationToken)

                    if page.Count = 0 then
                        logger.LogWarning("No songs returned on page {Page}, stopping", pageNumber)
                        keepGoing <- false
                    else
                        for song in page do
                            processed <- processed + 1

                            if not (isNull progress) then
                                progress.Report(struct (processed, total))

                            yield song

                        if pageNumber % 10 = 0 then
                            logger.LogDebug(
                                "Processed {Processed} songs (page {Page}/{MaxPage})",
                                processed,
                                pageNumber,
                                maxPage
                            )

                        pageNumber <- pageNumber + 1

                logger.LogInformation("Completed scraping {Processed} songs from Ignition4", processed)
            }
