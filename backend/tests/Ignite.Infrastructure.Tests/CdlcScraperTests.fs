module Ignite.Infrastructure.Tests.CdlcScraperTests

open System
open System.Collections.Generic
open System.IO
open System.Net
open System.Net.Http
open System.Text
open System.Text.Json
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Data
open Ignite.Infrastructure.Scraping
open Microsoft.EntityFrameworkCore
open Microsoft.Extensions.Logging.Abstractions
open Microsoft.Extensions.Options
open Xunit

type private StubHttpMessageHandler(respond: HttpRequestMessage -> HttpResponseMessage) =
    inherit HttpMessageHandler()

    override _.SendAsync(request, _) = Task.FromResult(respond request)

let private response (mediaType: string) (body: string) =
    let result = new HttpResponseMessage(HttpStatusCode.OK)
    result.Content <- new StringContent(body, Encoding.UTF8, mediaType)
    result

[<Fact>]
let ``scrapes songs when the Livewire snapshot is single quoted and formatted`` () =
    task {
        let requests = List<struct (HttpMethod * string * string)>()
        let nonComponentSnapshot = "{\"memo\":null}"
        let snapshot = "{ \"memo\": { \"name\": \"advanced-search\" } }"

        let searchPage =
            String.Concat(
                "<meta name=\"csrf-token\" content=\"csrf\">",
                "<script>window.livewireScriptConfig={\"uri\":\"\\/livewire-test\\/update\"}</script>",
                "<div wire:snapshot=\"",
                WebUtility.HtmlEncode(nonComponentSnapshot),
                "\"></div>",
                "<div wire:snapshot='",
                WebUtility.HtmlEncode(snapshot),
                "'></div>"
            )

        let songCard =
            "<div class=\"bg-neutral-900/80 border border-gray-700/70 rounded-lg shadow-lg overflow-hidden\">"
            + "<a href=\"/cdlc/42\">Download</a>"
            + "<h3>Test &amp; Song</h3>"
            + "<a href=\"/artist/7\">Test Artist</a>"
            + "<a href=\"/artist/7/album/test\">Test Album</a>"
            + "<a href=\"/profile/test-author\">Author</a>"
            + "<span class=\"part-lead\">Lead</span>"
            + "</div>"

        let livewireResponse =
            JsonSerializer.Serialize(
                {| components =
                    [| {| effects = {| html = songCard |}
                          snapshot = snapshot |} |] |}
            )

        use handler =
            new StubHttpMessageHandler(fun request ->
                let body =
                    if isNull request.Content then
                        ""
                    else
                        request.Content.ReadAsStringAsync().GetAwaiter().GetResult()

                requests.Add(struct (request.Method, request.RequestUri.AbsolutePath, body))

                match request.RequestUri.AbsolutePath with
                | "/" ->
                    response
                        "text/html"
                        "<meta name=\"csrf-token\" content=\"csrf\"><a href=\"/logout\">Logout</a>"
                | "/search/advanced" -> response "text/html" searchPage
                | "/livewire-test/update" -> response "application/json" livewireResponse
                | _ -> response "text/html" searchPage)

        use client = new HttpClient(handler)
        let config = CdlcScraperConfig()
        config.BaseUrl <- "https://ignition.test"
        config.MaxRequestsPerSecond <- 100
        config.MaxRetryAttempts <- 1

        let persistence =
            CookiePersistence(
                CookieContainer(),
                Path.Combine(Path.GetTempPath(), $"ignite-test-{Guid.NewGuid()}.json")
            )

        let scraper =
            CdlcScraper(client, Options.Create(config), NullLogger<CdlcScraper>.Instance, persistence)
            :> ICdlcScraper

        let songs = List<_>()
        let enumerator = scraper.ScrapeAllSongsAsync(null, CancellationToken.None).GetAsyncEnumerator()
        let mutable hasMore = true

        while hasMore do
            let! moved = enumerator.MoveNextAsync()
            hasMore <- moved

            if moved then
                songs.Add(enumerator.Current)

        do! enumerator.DisposeAsync()

        let song = Assert.Single(songs)
        Assert.Equal("Test & Song", song.Title)
        Assert.Equal("Test Artist", song.Artist)
        Assert.Equal("Test Album", song.Album)
        Assert.Equal("test-author", song.Author)
        Assert.True(song.Lead)
        Assert.Equal("https://ignition4.customsforge.com/cdlc/42", song.DownloadLink)

        Assert.Contains(requests, fun struct (_, path, _) -> path = "/search/advanced")

        let struct (_, _, livewireRequestBody) =
            requests
            |> Seq.find (fun struct (method, path, _) ->
                method = HttpMethod.Post && path = "/livewire-test/update")

        use livewireRequest = JsonDocument.Parse(livewireRequestBody)
        let sentSnapshot =
            livewireRequest.RootElement.GetProperty("components").[0].GetProperty("snapshot").GetString()

        Assert.Equal(snapshot, sentSnapshot)
        Assert.Contains("\"query\":\"*\"", livewireRequestBody)
    }

[<Fact>]
let ``reports an upstream error when advanced search redirects away from its configured route`` () =
    task {
        let sessionPage =
            "<meta name=\"csrf-token\" content=\"csrf\"><a href=\"/logout\">Logout</a>"

        use handler =
            new StubHttpMessageHandler(fun request ->
                match request.RequestUri.AbsolutePath with
                | "/" -> response "text/html" sessionPage
                | "/search/advanced" ->
                    let redirected = response "text/html" sessionPage
                    redirected.RequestMessage <- new HttpRequestMessage(HttpMethod.Get, "https://ignition.test/")
                    redirected
                | _ -> response "text/html" sessionPage)

        use client = new HttpClient(handler)
        let config = CdlcScraperConfig()
        config.BaseUrl <- "https://ignition.test"
        config.MaxRequestsPerSecond <- 100
        config.MaxRetryAttempts <- 1

        let persistence =
            CookiePersistence(
                CookieContainer(),
                Path.Combine(Path.GetTempPath(), $"ignite-test-{Guid.NewGuid()}.json")
            )

        let scraper =
            CdlcScraper(client, Options.Create(config), NullLogger<CdlcScraper>.Instance, persistence)
            :> ICdlcScraper

        let! error =
            Assert.ThrowsAsync<HttpRequestException>(fun () ->
                scraper.GetTotalSongCountAsync(CancellationToken.None))

        Assert.Contains("redirected", error.Message, StringComparison.OrdinalIgnoreCase)
    }

let private twoCardPage =
    "<div class=\"flex items-center gap-3\">community row wrapper</div>"
    + "<div class=\"bg-neutral-900/80 border border-gray-700/70 rounded-lg shadow-lg overflow-hidden\">"
    + "<a href=\"/cdlc/10\">Download</a><h3>Community Song</h3>"
    + "<a href=\"/artist/1\">Some Artist</a><a href=\"/artist/1/album/x\">X</a>"
    + "<a href=\"/profile/u1\">U1</a><span class=\"part-lead\">Lead</span></div>"
    + "<div class=\"flex items-center gap-3 bg-red-500'\":'row-false\">official row wrapper</div>"
    + "<div class=\"bg-neutral-900/80 border border-gray-700/70 rounded-lg shadow-lg overflow-hidden\">"
    + "<a href=\"/cdlc/20\">Download</a><h3>Official Song</h3>"
    + "<a href=\"/artist/2\">Big Band</a><a href=\"/artist/2/album/y\">Y</a>"
    + "<a href=\"/profile/u2\">U2</a><span class=\"part-bass\">Bass</span></div>"
    + "<div class=\"flex items-center gap-3\">another community row wrapper</div>"
    + "<div class=\"bg-neutral-900/80 border border-gray-700/70 rounded-lg shadow-lg overflow-hidden\">"
    + "<a href=\"/cdlc/30\">Download</a><h3>After Official</h3>"
    + "<a href=\"/artist/3\">Third Artist</a><a href=\"/artist/3/album/z\">Z</a>"
    + "<a href=\"/profile/u3\">U3</a></div>"

[<Fact>]
let ``flags only the official-DLC song using the red Ignition4 row indicator`` () =
    task {
        let snapshot = "{\"memo\":{\"name\":\"advanced-search\"}}"

        let searchPage =
            String.Concat(
                "<meta name=\"csrf-token\" content=\"csrf\">",
                "<script>window.livewireScriptConfig={\"uri\":\"\\/livewire-test\\/update\"}</script>",
                "<div wire:snapshot=\"",
                WebUtility.HtmlEncode(snapshot),
                "\"></div>"
            )

        let livewireResponse =
            JsonSerializer.Serialize(
                {| components =
                    [| {| effects = {| html = twoCardPage |}
                          snapshot = snapshot |} |] |}
            )

        use handler =
            new StubHttpMessageHandler(fun request ->
                match request.RequestUri.AbsolutePath with
                | "/" ->
                    response
                        "text/html"
                        "<meta name=\"csrf-token\" content=\"csrf\"><a href=\"/logout\">Logout</a>"
                | "/search/advanced" -> response "text/html" searchPage
                | "/livewire-test/update" -> response "application/json" livewireResponse
                | _ -> response "text/html" searchPage)

        use client = new HttpClient(handler)
        let config = CdlcScraperConfig()
        config.BaseUrl <- "https://ignition.test"
        config.MaxRequestsPerSecond <- 100
        config.MaxRetryAttempts <- 1

        let persistence =
            CookiePersistence(
                CookieContainer(),
                Path.Combine(Path.GetTempPath(), $"ignite-test-{Guid.NewGuid()}.json")
            )

        let scraper =
            CdlcScraper(client, Options.Create(config), NullLogger<CdlcScraper>.Instance, persistence)
            :> ICdlcScraper

        let songs = List<_>()
        let enumerator = scraper.ScrapeAllSongsAsync(null, CancellationToken.None).GetAsyncEnumerator()
        let mutable hasMore = true

        while hasMore do
            let! moved = enumerator.MoveNextAsync()
            hasMore <- moved

            if moved then
                songs.Add(enumerator.Current)

        do! enumerator.DisposeAsync()

        Assert.Equal(3, songs.Count)
        Assert.False(songs.[0].OfficialDlc)
        Assert.Equal("Community Song", songs.[0].Title)
        Assert.True(songs.[1].OfficialDlc)
        Assert.Equal("Official Song", songs.[1].Title)
        Assert.False(songs.[2].OfficialDlc)
        Assert.Equal("After Official", songs.[2].Title)
    }

[<Fact>]
let ``official DLC flag round-trips through the EF Core SQLite schema`` () =
    task {
        let dbPath = Path.Combine(Path.GetTempPath(), $"ignite-official-{Guid.NewGuid():N}.db")

        let options =
            DbContextOptionsBuilder<IgniteDbContext>()
                .UseSqlite($"Data Source={dbPath}")
                .Options

        use context = new IgniteDbContext(options)
        do! context.Database.EnsureCreatedAsync() :> Task

        let song = Song(OfficialDlc = true)
        song.Artist <- "Artist"
        song.Title <- "Title"
        song.Album <- "Album"
        song.DownloadLink <- "https://example.test/1"

        context.Songs.Add(song) |> ignore
        do! context.SaveChangesAsync() :> Task
        context.ChangeTracker.Clear()

        let! loaded = context.Songs.FirstOrDefaultAsync(fun s -> s.Artist = "Artist")
        Assert.True(loaded.OfficialDlc)
    }
