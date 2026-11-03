namespace Ignite.Infrastructure

open System
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
