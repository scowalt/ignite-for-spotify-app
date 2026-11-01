namespace Ignite.Infrastructure

open System
open System.Collections.Generic
open System.IO
open System.Net
open System.Net.Http
open System.Net.Security
open System.Net.Sockets
open System.Security.Cryptography.X509Certificates
open System.Runtime.CompilerServices
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Data
open Ignite.Infrastructure.Data.Repositories
open Ignite.Infrastructure.Scraping
open Ignite.Infrastructure.Spotify
open Microsoft.EntityFrameworkCore
open Microsoft.Extensions.Configuration
open Microsoft.Extensions.DependencyInjection

[<Extension>]
type DependencyInjection =

    [<Extension>]
    static member AddInfrastructure
        (
            services: IServiceCollection,
            configuration: IConfiguration,
            connectionString: string,
            requireExistingDatabase: bool
        ) =
        let validatedConnectionString =
            DatabaseConfiguration.validateConnectionString requireExistingDatabase connectionString

        services.AddDbContext<IgniteDbContext>(fun options ->
            options.UseSqlite(
                validatedConnectionString,
                fun sqliteOptions -> sqliteOptions.CommandTimeout(60) |> ignore
            )
            |> ignore

            options.EnableDetailedErrors() |> ignore
            options.EnableSensitiveDataLogging(false) |> ignore)
        |> ignore

        services.AddSingleton(DatabaseStartupOptions(requireExistingDatabase)) |> ignore

        let ipv6PreferringHandler () =
            let handler = SocketsHttpHandler()
            handler.SslOptions <- SslClientAuthenticationOptions(CertificateRevocationCheckMode = X509RevocationMode.NoCheck)

            handler.ConnectCallback <-
                fun context cancellationToken ->
                    ValueTask<Stream>(
                        task {
                            let! entry =
                                Dns.GetHostEntryAsync(context.DnsEndPoint.Host, cancellationToken)

                            let addresses =
                                entry.AddressList
                                |> Array.sortByDescending (fun a ->
                                    a.AddressFamily = AddressFamily.InterNetworkV6)

                            let socket = new Socket(SocketType.Stream, ProtocolType.Tcp)
                            socket.NoDelay <- true

                            try
                                do!
                                    socket.ConnectAsync(
                                        addresses,
                                        context.DnsEndPoint.Port,
                                        cancellationToken
                                    )

                                return new NetworkStream(socket, ownsSocket = true) :> Stream
                            with ex ->
                                socket.Dispose()
                                return raise ex
                        }
                    )

            handler :> HttpMessageHandler

        services.ConfigureHttpClientDefaults(fun builder ->
            builder.ConfigurePrimaryHttpMessageHandler(fun () -> ipv6PreferringHandler ())
            |> ignore)
        |> ignore

        services.AddScoped<ISongRepository, SongRepository>() |> ignore
        services.AddScoped<IUserSessionRepository, UserSessionRepository>() |> ignore
        services.AddScoped<IPlaylistSearchSnapshotRepository, PlaylistSearchSnapshotRepository>() |> ignore
        services.AddScoped<IScrapingJobRepository, ScrapingJobRepository>() |> ignore

        services.Configure<SpotifyConfig>(configuration.GetSection(SpotifyConfig.SectionName))
        |> ignore

        services.AddScoped<ISpotifyAuthService, SpotifyAuthService>() |> ignore
        services.AddSingleton<ISpotifyClientService, RateLimitedSpotifyClient>() |> ignore

        services.AddScoped<ISongMatchingService, Ignite.Matching.SongMatchingService>()
        |> ignore

        services.Configure<CdlcScraperConfig>(configuration.GetSection(CdlcScraperConfig.SectionName))
        |> ignore

        services.PostConfigure<CdlcScraperConfig>(fun (config: CdlcScraperConfig) ->
            if String.IsNullOrEmpty(config.Username) then
                let fromEnv = Environment.GetEnvironmentVariable("CDLC_SCRAPER_USERNAME")

                if not (String.IsNullOrEmpty(fromEnv)) then
                    config.Username <- fromEnv

            if String.IsNullOrEmpty(config.Password) then
                let fromEnv = Environment.GetEnvironmentVariable("CDLC_SCRAPER_PASSWORD")

                if not (String.IsNullOrEmpty(fromEnv)) then
                    config.Password <- fromEnv

            if String.IsNullOrEmpty(config.Cookies) then
                let fromEnv = Environment.GetEnvironmentVariable("CDLC_SCRAPER_COOKIES")

                if not (String.IsNullOrEmpty(fromEnv)) then
                    config.Cookies <- fromEnv)
        |> ignore

        let cookieContainer = CookieContainer()
        let cookiePersistence = CookiePersistence(cookieContainer, "/app/data/cookies.json")
        cookiePersistence.Load()
        services.AddSingleton(cookiePersistence) |> ignore

        services
            .AddHttpClient<ICdlcScraper, CdlcScraper>()
            .ConfigurePrimaryHttpMessageHandler(fun () ->
                new HttpClientHandler(UseCookies = true, CookieContainer = cookieContainer) :> HttpMessageHandler)
            .SetHandlerLifetime(Timeout.InfiniteTimeSpan)
        |> ignore

        services

    [<Extension>]
    static member InitializeDatabaseAsync(services: IServiceProvider) =
        task {
            let mutable attempt = 0
            let startupOptions = services.GetRequiredService<DatabaseStartupOptions>()
            let maxRetries = if startupOptions.RequireExisting then 1 else 5

            while attempt < maxRetries do
                try
                    use scope = services.CreateScope()
                    let context = scope.ServiceProvider.GetRequiredService<IgniteDbContext>()

                    if startupOptions.RequireExisting then
                        let! canConnect = context.Database.CanConnectAsync()

                        if not canConnect then
                            raise (InvalidDataException("The production SQLite database could not be opened."))

                        do! DependencyInjection.ValidateRequiredSchemaAsync(context)
                        do! DependencyInjection.EnsureOfficialDlcColumnAsync(context)
                        do! DependencyInjection.EnsurePlaylistSearchSnapshotsTableAsync(context)
                    else
                        do! context.Database.EnsureCreatedAsync() :> Task
                        do! DependencyInjection.EnsureOfficialDlcColumnAsync(context)
                        do! DependencyInjection.EnsurePlaylistSearchSnapshotsTableAsync(context)
                        do! DependencyInjection.CreateFtsTableAsync(context)

                    do! context.Database.ExecuteSqlRawAsync("PRAGMA journal_mode=WAL;") :> Task
                    attempt <- maxRetries
                with ex ->
                    attempt <- attempt + 1

                    if attempt >= maxRetries then
                        raise (AggregateException($"Database initialization failed after {maxRetries} attempts", ex))

                    let delay = TimeSpan.FromSeconds(float attempt * 2.0)
                    eprintfn $"Database initialization attempt {attempt} failed: {ex.Message}. Retrying in {delay.TotalSeconds}s..."
                    do! Task.Delay(delay)
        }
        :> Task

    static member private ValidateRequiredSchemaAsync(context: IgniteDbContext) : Task =
        task {
            let requiredObjects =
                dict
                    [ "songs", "table"
                      "user_sessions", "table"
                      "scraping_jobs", "table"
                      "songs_fts", "table"
                      "songs_ai", "trigger"
                      "songs_ad", "trigger"
                      "songs_au", "trigger" ]

            let connection = context.Database.GetDbConnection()
            do! connection.OpenAsync()
            use command = connection.CreateCommand()

            command.CommandText <-
                "SELECT name, type FROM sqlite_master WHERE name IN ('songs', 'user_sessions', 'scraping_jobs', 'songs_fts', 'songs_ai', 'songs_ad', 'songs_au')"

            use! reader = command.ExecuteReaderAsync()
            let found = Dictionary<string, string>(StringComparer.Ordinal)

            while reader.Read() do
                found.[reader.GetString(0)] <- reader.GetString(1)

            let missing =
                requiredObjects
                |> Seq.choose (fun pair ->
                    match found.TryGetValue(pair.Key) with
                    | true, objectType when objectType = pair.Value -> None
                    | _ -> Some $"{pair.Value} {pair.Key}")
                |> String.concat ", "

            if not (String.IsNullOrEmpty(missing)) then
                raise (InvalidDataException($"The production SQLite database is missing required schema objects: {missing}."))
        }
        :> Task

    static member private EnsureOfficialDlcColumnAsync(context: IgniteDbContext) : Task =
        task {
            let isAlreadyPresent (ex: exn) =
                not (isNull ex)
                && not (isNull ex.Message)
                && ex.Message.Contains("duplicate column name", StringComparison.OrdinalIgnoreCase)

            try
                do!
                    context.Database.ExecuteSqlRawAsync(
                        "ALTER TABLE songs ADD COLUMN official_dlc INTEGER NOT NULL DEFAULT 0"
                    )
                    :> Task
            with ex when isAlreadyPresent ex ->
                ()
        }
        :> Task

    static member private EnsurePlaylistSearchSnapshotsTableAsync(context: IgniteDbContext) : Task =
        task {
            do!
                context.Database.ExecuteSqlRawAsync(
                    """
                    CREATE TABLE IF NOT EXISTS playlist_search_snapshots (
                        id INTEGER NOT NULL CONSTRAINT pk_playlist_search_snapshots PRIMARY KEY AUTOINCREMENT,
                        spotify_user_id TEXT NOT NULL,
                        playlist_id TEXT NOT NULL,
                        results_json TEXT NOT NULL,
                        total_tracks INTEGER NOT NULL,
                        processed_tracks INTEGER NOT NULL,
                        matched_tracks INTEGER NOT NULL,
                        total_matches INTEGER NOT NULL,
                        skipped_tracks INTEGER NOT NULL,
                        failed_tracks INTEGER NOT NULL,
                        unprocessed_tracks INTEGER NOT NULL,
                        duration_ticks INTEGER NOT NULL,
                        generated_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                :> Task

            do!
                context.Database.ExecuteSqlRawAsync(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_playlist_search_snapshots_user_playlist
                    ON playlist_search_snapshots (spotify_user_id, playlist_id)
                    """
                )
                :> Task
        }
        :> Task

    static member private CreateFtsTableAsync(context: IgniteDbContext) : Task =
        task {
            let connection = context.Database.GetDbConnection()
            do! connection.OpenAsync()

            let mutable ftsExists = 0

            do!
                task {
                    use command = connection.CreateCommand()

                    command.CommandText <-
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='songs_fts'"

                    let! result = command.ExecuteScalarAsync()
                    ftsExists <- Convert.ToInt32(result)
                }
                :> Task

            if ftsExists = 0 then
                do!
                    context.Database.ExecuteSqlRawAsync(
                        "CREATE VIRTUAL TABLE songs_fts USING fts5(artist, title, album, content='songs', content_rowid='id')"
                    )
                    :> Task

                do!
                    context.Database.ExecuteSqlRawAsync(
                        "CREATE TRIGGER songs_ai AFTER INSERT ON songs BEGIN INSERT INTO songs_fts(rowid, artist, title, album) VALUES (new.id, new.artist, new.title, new.album); END"
                    )
                    :> Task

                do!
                    context.Database.ExecuteSqlRawAsync(
                        "CREATE TRIGGER songs_ad AFTER DELETE ON songs BEGIN INSERT INTO songs_fts(songs_fts, rowid, artist, title, album) VALUES ('delete', old.id, old.artist, old.title, old.album); END"
                    )
                    :> Task

                do!
                    context.Database.ExecuteSqlRawAsync(
                        "CREATE TRIGGER songs_au AFTER UPDATE ON songs BEGIN INSERT INTO songs_fts(songs_fts, rowid, artist, title, album) VALUES ('delete', old.id, old.artist, old.title, old.album); INSERT INTO songs_fts(rowid, artist, title, album) VALUES (new.id, new.artist, new.title, new.album); END"
                    )
                    :> Task

                do!
                    context.Database.ExecuteSqlRawAsync(
                        "INSERT INTO songs_fts(rowid, artist, title, album) SELECT id, artist, title, album FROM songs"
                    )
                    :> Task
        }
