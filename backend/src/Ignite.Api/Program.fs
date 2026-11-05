namespace Ignite.Api

#nowarn "3261"

open System
open System.Collections.Generic
open System.Linq
open System.Net.Http
open System.Text.Json
open System.Threading
open System.Threading.Tasks
open Hangfire
open Hangfire.Storage.SQLite
open Ignite.Api.Hubs
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure
open Ignite.Infrastructure.Data
open Ignite.Jobs.Jobs
open Microsoft.AspNetCore.Builder
open Microsoft.AspNetCore.Hosting
open Microsoft.AspNetCore.Http
open Microsoft.AspNetCore.SignalR
open Microsoft.Extensions.DependencyInjection
open Microsoft.Extensions.Hosting
open Microsoft.Extensions.Logging
open OpenTelemetry.Metrics
open OpenTelemetry.Resources
open System.Linq.Expressions
open Microsoft.Extensions.Configuration
open Sentry.AspNetCore
open Serilog
open SpotifyAPI.Web

[<CLIMutable>]
type SearchFromPlaylistRequest =
    { PlaylistId: string
      SessionId: string }

[<CLIMutable>]
type ExportToPlaylistRequest =
    { SongIds: List<int>
      PlaylistName: string
      Description: string | null
      IsPublic: bool }

[<CLIMutable>]
type CdlcSearchRequest =
    { Artist: string | null
      Title: string | null
      Album: string | null
      Author: string | null
      Lead: Nullable<bool>
      Rhythm: Nullable<bool>
      Bass: Nullable<bool>
      Vocals: Nullable<bool>
      DynamicDifficulty: Nullable<bool>
      HasSpotifyId: Nullable<bool>
      Page: int
      PageSize: int }

module SessionHelper =
    let getSpotifyUserId (session: UserSession) =
        if String.IsNullOrWhiteSpace(session.SpotifyUserId) then
            session.Id
        else
            session.SpotifyUserId

    let getValidSessionAsync
        (request: HttpRequest)
        (sessionRepo: IUserSessionRepository)
        (authService: ISpotifyAuthService)
        (cancellationToken: CancellationToken)
        =
        task {
            let sessionId = request.Cookies.["session_id"]

            if String.IsNullOrEmpty(sessionId) then
                return null
            else
                let! session = sessionRepo.GetByIdAsync(sessionId, cancellationToken)

                if isNull session then
                    return null
                elif session.TokenExpiresAt.HasValue && session.TokenExpiresAt.Value <= DateTime.UtcNow then
                    if String.IsNullOrEmpty(session.SpotifyRefreshToken) then
                        return null
                    else
                        try
                            let! tokens =
                                authService.RefreshTokenAsync(session.SpotifyRefreshToken, cancellationToken)

                            session.SpotifyAccessToken <- tokens.AccessToken
                            session.SpotifyRefreshToken <- tokens.RefreshToken
                            session.TokenExpiresAt <- tokens.ExpiresAt
                            do! sessionRepo.UpdateAsync(session, cancellationToken) :> Task
                            return session
                        with _ ->
                            return null
                elif String.IsNullOrEmpty(session.SpotifyAccessToken) then
                    return null
                else
                    return session
        }

    let deleteConnectedDataAsync
        (sessionId: string)
        (sessionRepo: IUserSessionRepository)
        (snapshotRepo: IPlaylistSearchSnapshotRepository)
        (cancellationToken: CancellationToken)
        =
        task {
            if not (String.IsNullOrEmpty(sessionId)) then
                let! session = sessionRepo.GetByIdAsync(sessionId, cancellationToken)

                if not (isNull session) then
                    do!
                        snapshotRepo.DeleteBySpotifyUserIdAsync(
                            getSpotifyUserId session,
                            cancellationToken
                        )

                    do! sessionRepo.DeleteAsync(session.Id, cancellationToken)
        }

module Program =

    [<EntryPoint>]
    let main args =
        Log.Logger <-
            LoggerConfiguration()
                .WriteTo.Console()
                .WriteTo.Sentry()
                .CreateBootstrapLogger()

        try
          try
            Log.Information("Starting Ignite for Spotify API")

            let builder = WebApplication.CreateBuilder(args)

            (builder.WebHost :> Microsoft.AspNetCore.Hosting.IWebHostBuilder).UseSentry(fun (options: SentryAspNetCoreOptions) ->
                options.Dsn <- builder.Configuration.["Sentry:Dsn"]
                options.Environment <- builder.Environment.EnvironmentName
                options.SendDefaultPii <- false
                options.MinimumBreadcrumbLevel <- Microsoft.Extensions.Logging.LogLevel.Information
                options.MinimumEventLevel <- Microsoft.Extensions.Logging.LogLevel.Error
                options.SetBeforeSend(fun sentryEvent ->
                    let ex = sentryEvent.Exception
                    let message = sentryEvent.Message

                    let isTransientScraperFailure =
                        ex <> null
                        && (ex :? System.Net.Http.HttpRequestException
                            || ex :? System.Threading.Tasks.TaskCanceledException
                            || ex :? System.OperationCanceledException)
                        && (let stackTrace = ex.ToString()
                            stackTrace.Contains("CdlcScraper") || stackTrace.Contains("ScrapeCdlcJob"))

                    let isRetriedDatabaseConnectionDiagnostic =
                        ex = null
                        && message <> null
                        && message.Message
                           = "An error occurred using the connection to database '{database}' on server '{server}'."

                    if isTransientScraperFailure || isRetriedDatabaseConnectionDiagnostic then
                        null
                    else
                        sentryEvent))
            |> ignore

            builder.Host.UseSerilog(fun context services configuration ->
                configuration
                    .ReadFrom.Configuration(context.Configuration)
                    .ReadFrom.Services(services)
                    .Enrich.FromLogContext()
                    .WriteTo.Console()
                    .WriteTo.Sentry()
                |> ignore)
            |> ignore

            builder.Services.AddOpenApi() |> ignore
            builder.Services.AddEndpointsApiExplorer() |> ignore
            builder.Services.AddSwaggerGen() |> ignore

            builder.Services.AddSignalR() |> ignore

            builder.Services
                .AddOpenTelemetry()
                .ConfigureResource(fun resource -> resource.AddService(serviceName = "ignite-api") |> ignore)
                .WithMetrics(fun metrics ->
                    metrics
                        .AddAspNetCoreInstrumentation()
                        .AddRuntimeInstrumentation()
                        .AddPrometheusExporter()
                    |> ignore)
            |> ignore

            builder.Services.AddCors(fun options ->
                options.AddDefaultPolicy(fun policy ->
                    let origins =
                        builder.Configuration.GetValue<string>("Cors:Origins")

                    let originsValue =
                        if isNull origins then "http://localhost:5173" else origins

                    policy
                        .WithOrigins(originsValue)
                        .AllowAnyHeader()
                        .AllowAnyMethod()
                        .AllowCredentials()
                    |> ignore))
            |> ignore

            let connectionString, requireExistingDatabase =
                DatabaseBootstrap.initialize builder.Configuration builder.Environment

            builder.Services.AddInfrastructure(
                builder.Configuration,
                connectionString,
                requireExistingDatabase
            )
            |> ignore

            let mutable hangfireConnectionString =
                builder.Configuration.GetConnectionString("Hangfire")

            if String.IsNullOrEmpty(hangfireConnectionString) then
                hangfireConnectionString <- "/app/data/hangfire.db"

            if
                hangfireConnectionString.StartsWith("Data Source=", StringComparison.OrdinalIgnoreCase)
            then
                hangfireConnectionString <- hangfireConnectionString.["Data Source=".Length ..]

            builder.Services.AddHangfire(fun config ->
                config
                    .SetDataCompatibilityLevel(CompatibilityLevel.Version_180)
                    .UseSimpleAssemblyNameTypeSerializer()
                    .UseRecommendedSerializerSettings()
                    .UseSQLiteStorage(
                        hangfireConnectionString,
                        SQLiteStorageOptions(
                            DistributedLockLifetime = TimeSpan.FromMinutes(5.0),
                            QueuePollInterval = TimeSpan.FromSeconds(30.0)
                        )
                    )
                |> ignore)
            |> ignore

            builder.Services.AddHangfireServer(fun (options: BackgroundJobServerOptions) ->
                options.Queues <- [| "default"; "scraping"; "matching" |])
            |> ignore

            builder.Services.AddScoped<ScrapeCdlcJob>() |> ignore
            builder.Services.AddScoped<UpdateSpotifyIdsJob>() |> ignore
            builder.Services.AddScoped<PlaylistSearchJob>() |> ignore

            builder.Services.AddSingleton<IHubNotificationService, HubNotificationService>()
            |> ignore

            builder.Services.AddHttpClient(
                "github-stars",
                fun (client: HttpClient) -> client.Timeout <- TimeSpan.FromSeconds 5.0
            )
            |> ignore

            builder.Services.AddSingleton<GitHubStarsCache>(fun services ->
                let clients = services.GetRequiredService<IHttpClientFactory>()

                GitHubStarsCache(
                    (fun ct -> GitHubStars.fetchFromGitHub (clients.CreateClient "github-stars") ct),
                    TimeProvider.System,
                    services.GetRequiredService<ILogger<GitHubStarsCache>>()
                ))
            |> ignore

            let app = builder.Build()

            app.UseSerilogRequestLogging() |> ignore
            app.Use(RequestCancellationMiddleware.invoke) |> ignore
            app.UseOpenTelemetryPrometheusScrapingEndpoint() |> ignore

            if app.Environment.IsDevelopment() then
                app.MapOpenApi() |> ignore
                app.UseSwagger() |> ignore
                app.UseSwaggerUI() |> ignore

            app.UseCors() |> ignore

            app.UseHangfireDashboard(
                "/hangfire",
                DashboardOptions(Authorization = Array.empty)
            )
            |> ignore

            let scrapeParam = Expression.Parameter(typeof<ScrapeCdlcJob>, "job")
            let scrapeMethod = typeof<ScrapeCdlcJob>.GetMethod("ExecuteAsync")
            let scrapeCall =
                Expression.Call(
                    scrapeParam,
                    scrapeMethod,
                    Expression.Constant(null, typeof<Hangfire.Server.PerformContext>),
                    Expression.Constant(CancellationToken.None)
                )
            let scrapeExpr = Expression.Lambda<Func<ScrapeCdlcJob, Task>>(scrapeCall, scrapeParam)

            RecurringJob.AddOrUpdate<ScrapeCdlcJob>(
                "scrape-cdlc",
                scrapeExpr,
                "0 2 * * *",
                RecurringJobOptions(TimeZone = TimeZoneInfo.FindSystemTimeZoneById("America/New_York"))
            )

            app.MapHub<SearchHub>("/hubs/search") |> ignore

            app.MapGet(
                "/health",
                Func<IResult>(fun () -> Results.Ok({| status = "healthy" |}))
            )
                .WithName("HealthCheck")
                .WithTags("Health")
            |> ignore

            app.MapGet(
                "/health/ready",
                Func<IgniteDbContext, ILoggerFactory, CancellationToken, Task<IResult>>(fun context loggerFactory ct ->
                    task {
                        try
                            let! readiness = DatabaseReadiness.checkAsync context ct

                            match readiness with
                            | Ready ->
                                return Results.Ok({| status = "healthy" |})
                            | Unavailable error ->
                                match error with
                                | Some ex ->
                                    loggerFactory
                                        .CreateLogger("DatabaseReadiness")
                                        .LogError(ex, "Application database readiness check failed")
                                | None -> ()

                                return
                                    Results.Json(
                                        {| status = "unhealthy" |},
                                        statusCode = DatabaseReadiness.statusCode readiness
                                    )
                        with
                        | :? OperationCanceledException ->
                            return raise (OperationCanceledException(ct))
                    })
            )
                .WithName("DatabaseReadiness")
                .WithTags("Health")
            |> ignore

            app.MapGet(
                "/api/github/stars",
                Func<GitHubStarsCache, HttpContext, CancellationToken, Task<IResult>>(fun cache context ct ->
                    task {
                        let! stars = cache.GetAsync(ct)
                        context.Response.Headers.CacheControl <- "public, max-age=300"

                        let count =
                            match stars with
                            | Some count -> Nullable count
                            | None -> Nullable()

                        return Results.Ok({| stars = count |})
                    })
            )
                .WithName("GetGitHubStars")
                .WithTags("GitHub")
            |> ignore

            app.MapGet(
                "/api/songs/stats",
                Func<ISongRepository, CancellationToken, Task<IResult>>(fun songRepo ct ->
                    task {
                        let! struct (total, withSpotify) = songRepo.GetStatsAsync(ct)

                        return
                            Results.Ok(
                                {| totalSongs = total
                                   songsWithSpotifyId = withSpotify
                                   percentageWithSpotify =
                                    if total > 0 then
                                        Math.Round(float withSpotify / float total * 100.0, 2)
                                    else
                                        0.0 |}
                            )
                    })
            )
                .WithName("GetStats")
                .WithTags("Songs")
            |> ignore

            app.MapGet(
                "/api/songs",
                Func<ISongRepository, CancellationToken, string, string, string, string, Nullable<bool>, Nullable<bool>, Nullable<bool>, Nullable<bool>, Nullable<bool>, int, int, Task<IResult>>
                    (fun songRepo ct artist title album author lead rhythm bass vocals dynamicDifficulty page pageSize ->
                        task {
                            let filter =
                                SongSearchFilter(
                                    Artist = artist,
                                    Title = title,
                                    Album = album,
                                    Author = author,
                                    Lead = lead,
                                    Rhythm = rhythm,
                                    Bass = bass,
                                    Vocals = vocals,
                                    DynamicDifficulty = dynamicDifficulty
                                )

                            let! result = songRepo.SearchAsync(filter, page, pageSize, ct)
                            return Results.Ok(result)
                        })
            )
                .WithName("SearchSongs")
                .WithTags("Songs")
            |> ignore

            app.MapGet(
                "/api/songs/{id:int}",
                Func<int, ISongRepository, CancellationToken, Task<IResult>>(fun id songRepo ct ->
                    task {
                        let! song = songRepo.GetByIdAsync(id, ct)

                        if not (isNull song) then
                            return Results.Ok(song)
                        else
                            return Results.NotFound()
                    })
            )
                .WithName("GetSongById")
                .WithTags("Songs")
            |> ignore

            app.MapGet(
                "/api/songs/search",
                Func<ISongRepository, string, int, CancellationToken, Task<IResult>>(fun songRepo q limit ct ->
                    task {
                        let! results = songRepo.FullTextSearchAsync(q, limit, ct)
                        return Results.Ok(results)
                    })
            )
                .WithName("FullTextSearchSongs")
                .WithTags("Songs")
            |> ignore


            app.MapGet(
                "/api/auth/login",
                Func<ISpotifyAuthService, IResult>(fun authService ->
                    let state = Guid.NewGuid().ToString("N")
                    let authUrl = authService.GetAuthorizationUrl(state)
                    Results.Redirect(authUrl))
            )
                .WithName("SpotifyLogin")
                .WithTags("Auth")
            |> ignore

            app.MapGet(
                "/api/auth/callback",
                Func<ISpotifyAuthService, IUserSessionRepository, HttpContext, string, string, CancellationToken, Task<IResult>>
                    (fun authService sessionRepo httpContext code state cancellationToken ->
                        task {
                            try
                                let! tokens = authService.ExchangeCodeAsync(code, cancellationToken)

                                let! profile =
                                    authService.GetUserProfileAsync(tokens.AccessToken, cancellationToken)

                                let session = UserSession()
                                session.Id <- UserSessionId.create ()
                                session.SpotifyUserId <- profile.Id
                                session.SpotifyAccessToken <- tokens.AccessToken
                                session.SpotifyRefreshToken <- tokens.RefreshToken
                                session.TokenExpiresAt <- tokens.ExpiresAt
                                do! sessionRepo.CreateAsync(session, cancellationToken) :> Task

                                httpContext.Response.Cookies.Append(
                                    "session_id",
                                    session.Id,
                                    CookieOptions(
                                        HttpOnly = true,
                                        Secure = true,
                                        SameSite = SameSiteMode.Lax,
                                        Expires = DateTimeOffset(DateTime.UtcNow.AddDays(30.0))
                                    )
                                )

                                return Results.Redirect("/")
                            with ex ->
                                match OAuthCallbackFailure.tryGetRedirect ex with
                                | Some redirect ->
                                    Log.Warning(
                                        "Spotify OAuth authorization code was invalid or expired; asking user to sign in again"
                                    )
                                    return Results.Redirect(redirect)
                                | None ->
                                    Log.Error(ex, "OAuth callback failed")
                                    return Results.Redirect("/?error=auth_failed")
                        })
            )
                .WithName("SpotifyCallback")
                .WithTags("Auth")
            |> ignore

            app.MapGet(
                "/api/auth/session",
                Func<ISpotifyAuthService, IUserSessionRepository, HttpRequest, CancellationToken, Task<IResult>>
                    (fun authService sessionRepo request cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            else
                                try
                                    let! profile =
                                        authService.GetUserProfileAsync(
                                            session.SpotifyAccessToken,
                                            cancellationToken
                                        )

                                    return
                                        Results.Ok(
                                            {| sessionId = session.Id
                                               profile =
                                                {| id = profile.Id
                                                   displayName = profile.DisplayName
                                                   imageUrl = profile.ImageUrl |}
                                               expiresAt = session.TokenExpiresAt |}
                                        )
                                with _ ->
                                    return Results.Unauthorized()
                        })
            )
                .WithName("GetSession")
                .WithTags("Auth")
            |> ignore

            app.MapPost(
                "/api/auth/logout",
                Func<IUserSessionRepository, IPlaylistSearchSnapshotRepository, HttpContext, CancellationToken, Task<IResult>>
                    (fun sessionRepo snapshotRepo httpContext cancellationToken ->
                        task {
                            let sessionId = httpContext.Request.Cookies.["session_id"]

                            do!
                                SessionHelper.deleteConnectedDataAsync
                                    sessionId
                                    sessionRepo
                                    snapshotRepo
                                    cancellationToken

                            httpContext.Response.Cookies.Delete("session_id")
                            return Results.Ok()
                        })
            )
                .WithName("Logout")
                .WithTags("Auth")
            |> ignore

            app.MapPost(
                "/api/auth/refresh",
                Func<ISpotifyAuthService, IUserSessionRepository, HttpContext, CancellationToken, Task<IResult>>
                    (fun authService sessionRepo httpContext cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    httpContext.Request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            elif String.IsNullOrEmpty(session.SpotifyRefreshToken) then
                                return Results.Unauthorized()
                            else
                                try
                                    let! tokens =
                                        authService.RefreshTokenAsync(
                                            session.SpotifyRefreshToken,
                                            cancellationToken
                                        )

                                    session.SpotifyAccessToken <- tokens.AccessToken
                                    session.SpotifyRefreshToken <- tokens.RefreshToken
                                    session.TokenExpiresAt <- tokens.ExpiresAt
                                    do! sessionRepo.UpdateAsync(session, cancellationToken) :> Task

                                    httpContext.Response.Cookies.Append(
                                        "session_id",
                                        session.Id,
                                        CookieOptions(
                                            HttpOnly = true,
                                            Secure = true,
                                            SameSite = SameSiteMode.Lax,
                                            Expires = DateTimeOffset(DateTime.UtcNow.AddDays(30.0))
                                        )
                                    )

                                    let! profile =
                                        authService.GetUserProfileAsync(
                                            tokens.AccessToken,
                                            cancellationToken
                                        )

                                    return
                                        Results.Ok(
                                            {| sessionId = session.Id
                                               profile =
                                                {| id = profile.Id
                                                   displayName = profile.DisplayName
                                                   imageUrl = profile.ImageUrl |}
                                               expiresAt = tokens.ExpiresAt |}
                                        )
                                with ex ->
                                    Log.Error(
                                        ex,
                                        "Token refresh failed for session {SessionId}",
                                        session.Id
                                    )

                                    return Results.Unauthorized()
                        })
            )
                .WithName("RefreshToken")
                .WithTags("Auth")
            |> ignore

            app.MapGet(
                "/api/auth/me",
                Func<ISpotifyAuthService, IUserSessionRepository, HttpRequest, CancellationToken, Task<IResult>>
                    (fun authService sessionRepo request cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            else
                                try
                                    let! profile =
                                        authService.GetUserProfileAsync(
                                            session.SpotifyAccessToken,
                                            cancellationToken
                                        )

                                    return
                                        Results.Ok(
                                            {| id = profile.Id
                                               displayName = profile.DisplayName
                                               imageUrl = profile.ImageUrl |}
                                        )
                                with ex ->
                                    Log.Error(
                                        ex,
                                        "Failed to get user profile for session {SessionId}",
                                        session.Id
                                    )

                                    return
                                        Results.BadRequest(
                                            {| error = "Failed to get profile"
                                               message = ex.Message |}
                                        )
                        })
            )
                .WithName("GetCurrentUser")
                .WithTags("Auth")
            |> ignore


            app.MapGet(
                "/api/spotify/playlists",
                Func<ISpotifyClientService, ISpotifyAuthService, IUserSessionRepository, HttpRequest, CancellationToken, Task<IResult>>
                    (fun spotifyClient authService sessionRepo request cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            else
                                let! playlists =
                                    spotifyClient.GetUserPlaylistsAsync(
                                        session.SpotifyAccessToken,
                                        cancellationToken
                                    )

                                return Results.Ok(playlists)
                        })
            )
                .WithName("GetUserPlaylists")
                .WithTags("Spotify")
            |> ignore

            app.MapGet(
                "/api/spotify/playlists/{playlistId}",
                Func<string, ISpotifyClientService, ISpotifyAuthService, IUserSessionRepository, HttpRequest, CancellationToken, Task<IResult>>
                    (fun playlistId spotifyClient authService sessionRepo request cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            else
                                try
                                    let! playlist =
                                        spotifyClient.GetPlaylistAsync(
                                            session.SpotifyAccessToken,
                                            playlistId,
                                            cancellationToken
                                        )

                                    return Results.Ok(playlist)
                                with
                                | :? APIException as ex when
                                    ex.Response <> null
                                    && ex.Response.StatusCode = Net.HttpStatusCode.NotFound
                                    ->
                                    return
                                        Results.NotFound(
                                            {| error = "playlist_not_found"
                                               message = "This playlist is private or does not exist." |}
                                        )
                                | :? APIException as ex when
                                    ex.Response <> null
                                    && ex.Response.StatusCode = Net.HttpStatusCode.Forbidden
                                    ->
                                    return
                                        Results.Json(
                                            {| error = "playlist_inaccessible"
                                               message = "You do not have access to this playlist." |},
                                            statusCode = 403
                                        )
                                | ex ->
                                    Log.Error(ex, "Failed to get playlist {PlaylistId}", playlistId)

                                    return
                                        Results.BadRequest(
                                            {| error = "playlist_fetch_failed"
                                               message = ex.Message |}
                                        )
                        })
            )
                .WithName("GetPlaylist")
                .WithTags("Spotify")
            |> ignore

            app.MapGet(
                "/api/spotify/playlists/{playlistId}/tracks",
                Func<string, ISpotifyClientService, ISpotifyAuthService, IUserSessionRepository, HttpRequest, CancellationToken, Task<IResult>>
                    (fun playlistId spotifyClient authService sessionRepo request cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            else
                                let! tracks =
                                    spotifyClient.GetPlaylistTracksAsync(
                                        session.SpotifyAccessToken,
                                        playlistId,
                                        cancellationToken
                                    )

                                return Results.Ok(tracks)
                        })
            )
                .WithName("GetPlaylistTracks")
                .WithTags("Spotify")
            |> ignore


            app.MapPost(
                "/api/jobs/scrape",
                Func<IBackgroundJobClient, IResult>(fun jobClient ->
                    let p = Expression.Parameter(typeof<ScrapeCdlcJob>, "job")
                    let methodInfo = typeof<ScrapeCdlcJob>.GetMethod("ExecuteAsync")
                    let call =
                        Expression.Call(
                            p,
                            methodInfo,
                            Expression.Constant(null, typeof<Hangfire.Server.PerformContext>),
                            Expression.Constant(CancellationToken.None)
                        )
                    let expr = Expression.Lambda<Func<ScrapeCdlcJob, Task>>(call, p)
                    let jobId = jobClient.Enqueue<ScrapeCdlcJob>(expr)
                    Results.Ok({| jobId = jobId; message = "Scrape job queued" |}))
            )
                .WithName("StartScrapeJob")
                .WithTags("Jobs")
            |> ignore

            app.MapPost(
                "/api/jobs/match-spotify",
                Func<IBackgroundJobClient, ISpotifyAuthService, IUserSessionRepository, HttpRequest, Nullable<int>, CancellationToken, Task<IResult>>
                    (fun jobClient authService sessionRepo request maxSongs cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            else
                                let maxSongsValue =
                                    if maxSongs.HasValue then maxSongs.Value else 1000

                                let p = Expression.Parameter(typeof<UpdateSpotifyIdsJob>, "job")
                                let methodInfo = typeof<UpdateSpotifyIdsJob>.GetMethod("ExecuteAsync")
                                let call =
                                    Expression.Call(
                                        p,
                                        methodInfo,
                                        Expression.Constant(session.Id, typeof<string>),
                                        Expression.Constant(maxSongsValue, typeof<int>),
                                        Expression.Constant(null, typeof<Hangfire.Server.PerformContext>),
                                        Expression.Constant(CancellationToken.None)
                                    )
                                let expr = Expression.Lambda<Func<UpdateSpotifyIdsJob, Task>>(call, p)
                                let jobId =
                                    jobClient.Enqueue<UpdateSpotifyIdsJob>(expr)

                                return
                                    Results.Ok(
                                        {| jobId = jobId
                                           message = "Spotify matching job queued" |}
                                    )
                        })
            )
                .WithName("StartSpotifyMatchJob")
                .WithTags("Jobs")
            |> ignore

            app.MapGet(
                "/api/jobs/scrape/status",
                Func<IScrapingJobRepository, CancellationToken, Task<IResult>>(fun scrapingJobRepo cancellationToken ->
                    task {
                        let! latestJob = scrapingJobRepo.GetLatestAsync(Nullable(), cancellationToken)

                        if isNull latestJob then
                            return
                                Results.Ok(
                                    {| status = "none"
                                       message = "No scraping jobs have been run" |}
                                )
                        else
                            return
                                Results.Ok(
                                    {| id = latestJob.Id
                                       status = latestJob.Status.ToString().ToLowerInvariant()
                                       jobType = latestJob.JobType.ToString()
                                       startedAt = latestJob.StartedAt
                                       completedAt = latestJob.CompletedAt
                                       songsProcessed = latestJob.SongsProcessed
                                       songsAdded = latestJob.SongsAdded
                                       songsUpdated = latestJob.SongsUpdated
                                       errorMessage = latestJob.ErrorMessage |}
                                )
                    })
            )
                .WithName("GetScrapeJobStatus")
                .WithTags("Jobs")
            |> ignore


            app.MapGet(
                "/api/search/from-playlist/{playlistId}",
                Func<string, IPlaylistSearchSnapshotRepository, ISpotifyAuthService, IUserSessionRepository, HttpRequest, CancellationToken, Task<IResult>>
                    (fun playlistId snapshotRepo authService sessionRepo request cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            elif String.IsNullOrWhiteSpace(playlistId) then
                                return Results.BadRequest({| message = "Playlist ID is required." |})
                            else
                                let! snapshot =
                                    snapshotRepo.GetLatestAsync(
                                        SessionHelper.getSpotifyUserId session,
                                        playlistId,
                                        cancellationToken
                                    )

                                if isNull snapshot then
                                    return Results.NotFound()
                                else
                                    use resultsDocument = JsonDocument.Parse(snapshot.ResultsJson)
                                    let results = resultsDocument.RootElement.Clone()

                                    return
                                        Results.Ok(
                                            {| playlistId = snapshot.PlaylistId
                                               generatedAt =
                                                DateTime.SpecifyKind(
                                                    snapshot.GeneratedAt,
                                                    DateTimeKind.Utc
                                                )
                                               results = results
                                               completion =
                                                {| totalTracks = snapshot.TotalTracks
                                                   processedTracks = snapshot.ProcessedTracks
                                                   matchedTracks = snapshot.MatchedTracks
                                                   totalMatches = snapshot.TotalMatches
                                                   skippedTracks = snapshot.SkippedTracks
                                                   failedTracks = snapshot.FailedTracks
                                                   unprocessedTracks = snapshot.UnprocessedTracks
                                                   isComplete = true
                                                   failureReason = null
                                                   duration = TimeSpan.FromTicks(snapshot.DurationTicks) |} |}
                                        )
                        })
            )
                .WithName("GetLatestPlaylistSearch")
                .WithTags("Search")
            |> ignore

            app.MapPost(
                "/api/search/from-playlist",
                Func<IBackgroundJobClient, ISpotifyAuthService, IUserSessionRepository, HttpRequest, SearchFromPlaylistRequest, CancellationToken, Task<IResult>>
                    (fun jobClient authService sessionRepo request searchRequest cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            elif
                                String.IsNullOrWhiteSpace(searchRequest.PlaylistId)
                                || String.IsNullOrWhiteSpace(searchRequest.SessionId)
                            then
                                return Results.BadRequest({| message = "Playlist ID and search session ID are required." |})
                            else
                                let jobId =
                                    PlaylistSearchQueue.enqueue
                                        jobClient
                                        session.Id
                                        searchRequest.PlaylistId
                                        searchRequest.SessionId

                                return
                                    PlaylistSearchQueue.acceptedResult
                                        jobId
                                        searchRequest.PlaylistId
                                        searchRequest.SessionId
                        })
            )
                .WithName("SearchFromPlaylist")
                .WithTags("Search")
            |> ignore

            app.MapPost(
                "/api/export/to-playlist",
                Func<ISpotifyClientService, ISongRepository, ISpotifyAuthService, IUserSessionRepository, HttpRequest, ExportToPlaylistRequest, CancellationToken, Task<IResult>>
                    (fun spotifyClient songRepo authService sessionRepo request exportRequest cancellationToken ->
                        task {
                            let! session =
                                SessionHelper.getValidSessionAsync
                                    request
                                    sessionRepo
                                    authService
                                    cancellationToken

                            if isNull session then
                                return Results.Unauthorized()
                            else
                                let songs = List<Song>()

                                for songId in exportRequest.SongIds do
                                    let! song = songRepo.GetByIdAsync(songId, cancellationToken)

                                    if not (isNull song) && not (String.IsNullOrEmpty(song.SpotifyTrackId)) then
                                        songs.Add(song)

                                if songs.Count = 0 then
                                    return
                                        Results.BadRequest(
                                            {| error = "No songs with Spotify IDs found" |}
                                        )
                                else
                                    let! playlist =
                                        spotifyClient.CreatePlaylistAsync(
                                            session.SpotifyAccessToken,
                                            exportRequest.PlaylistName,
                                            exportRequest.Description,
                                            exportRequest.IsPublic,
                                            cancellationToken
                                        )

                                    let trackIds =
                                        songs
                                        |> Seq.filter (fun s ->
                                            not (String.IsNullOrEmpty(s.SpotifyTrackId)))
                                        |> Seq.map (fun s -> s.SpotifyTrackId)
                                        |> Seq.toList

                                    do!
                                        spotifyClient.AddTracksToPlaylistAsync(
                                            session.SpotifyAccessToken,
                                            playlist.Id,
                                            trackIds,
                                            cancellationToken
                                        )

                                    return
                                        Results.Ok(
                                            {| playlist =
                                                {| id = playlist.Id
                                                   name = playlist.Name
                                                   description = playlist.Description
                                                   totalTracks = trackIds.Length
                                                   imageUrl = playlist.ImageUrl |}
                                               tracksAdded = trackIds.Length
                                               tracksSkipped =
                                                exportRequest.SongIds.Count - trackIds.Length |}
                                        )
                        })
            )
                .WithName("ExportToPlaylist")
                .WithTags("Export")
            |> ignore

            app.MapPost(
                "/api/search/cdlc",
                Func<ISongRepository, CdlcSearchRequest, CancellationToken, Task<IResult>>
                    (fun songRepo searchRequest cancellationToken ->
                        task {
                            let filter =
                                SongSearchFilter(
                                    Artist = searchRequest.Artist,
                                    Title = searchRequest.Title,
                                    Album = searchRequest.Album,
                                    Author = searchRequest.Author,
                                    Lead = searchRequest.Lead,
                                    Rhythm = searchRequest.Rhythm,
                                    Bass = searchRequest.Bass,
                                    Vocals = searchRequest.Vocals,
                                    DynamicDifficulty = searchRequest.DynamicDifficulty,
                                    HasSpotifyId = searchRequest.HasSpotifyId
                                )

                            let! result =
                                songRepo.SearchAsync(
                                    filter,
                                    searchRequest.Page,
                                    searchRequest.PageSize,
                                    cancellationToken
                                )

                            return
                                Results.Ok(
                                    {| items =
                                        result.Items
                                        |> Seq.map (fun s ->
                                            {| id = s.Id
                                               artist = s.Artist
                                               title = s.Title
                                               album = s.Album
                                               author = s.Author
                                               version = s.Version
                                               tuning = s.Tuning
                                               lead = s.Lead
                                               rhythm = s.Rhythm
                                               bass = s.Bass
                                               vocals = s.Vocals
                                               dynamicDifficulty = s.DynamicDifficulty
                                               officialDlc = s.OfficialDlc
                                               downloadLink = s.DownloadLink
                                               spotifyTrackId = s.SpotifyTrackId
                                               hasSpotifyMatch =
                                                not (String.IsNullOrEmpty(s.SpotifyTrackId)) |})
                                       totalCount = result.TotalCount
                                       page = result.Page
                                       pageSize = result.PageSize
                                       hasMore = result.HasMore |}
                                )
                        })
            )
                .WithName("SearchCdlc")
                .WithTags("Search")
            |> ignore

            app.Run()
            0
          with ex ->
            Log.Fatal(ex, "Application terminated unexpectedly")
            1
        finally
            Log.CloseAndFlush()
