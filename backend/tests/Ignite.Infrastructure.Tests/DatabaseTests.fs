module Ignite.Infrastructure.Tests.DatabaseTests

open System
open System.IO
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure
open Ignite.Infrastructure.Data
open Ignite.Infrastructure.Data.Repositories
open Microsoft.Data.Sqlite
open Microsoft.EntityFrameworkCore
open Microsoft.EntityFrameworkCore.Diagnostics
open Microsoft.Extensions.Configuration
open Microsoft.Extensions.DependencyInjection
open Xunit

let private createTempDirectory () =
    let path = Path.Combine(Path.GetTempPath(), $"ignite-database-tests-{Guid.NewGuid():N}")
    Directory.CreateDirectory(path) |> ignore
    path

let private deleteTempDirectory path =
    if Directory.Exists(path) then
        Directory.Delete(path, true)

let private createProvider databasePath requireExisting =
    let configuration = ConfigurationBuilder().Build()
    let services = ServiceCollection()

    services.AddInfrastructure(
        configuration,
        $"Data Source={databasePath};Default Timeout=60",
        requireExisting
    )
    |> ignore

    services.BuildServiceProvider()

type FailOnceConnectionInterceptor() =
    inherit DbConnectionInterceptor()

    let mutable shouldFail = true

    override _.ConnectionOpeningAsync(_, _, result, _) =
        if shouldFail then
            shouldFail <- false
            raise (InvalidOperationException("Simulated transient database connection failure."))

        ValueTask<InterceptionResult>(result)

let private createBareSchemaAsync databasePath =
    task {
        let options =
            DbContextOptionsBuilder<IgniteDbContext>()
                .UseSqlite($"Data Source={databasePath}")
                .Options

        use context = new IgniteDbContext(options)
        let! _ = context.Database.EnsureCreatedAsync()
        return ()
    }

[<Fact>]
let ``file database initializes WAL CRUD FTS and concurrent contexts`` () =
    task {
        let directory = createTempDirectory ()

        try
            let databasePath = Path.Combine(directory, "ignite.db")
            use provider = createProvider databasePath false
            do! provider.InitializeDatabaseAsync()

            use connection = new SqliteConnection($"Data Source={databasePath}")
            do! connection.OpenAsync()
            use journalCommand = connection.CreateCommand()
            journalCommand.CommandText <- "PRAGMA journal_mode;"
            let! journalMode = journalCommand.ExecuteScalarAsync()
            Assert.Equal("wal", Convert.ToString(journalMode).ToLowerInvariant())

            use writeScope = provider.CreateScope()
            use readScope = provider.CreateScope()
            let writer = writeScope.ServiceProvider.GetRequiredService<ISongRepository>()
            let reader = readScope.ServiceProvider.GetRequiredService<ISongRepository>()
            let song =
                Song(
                    Artist = "Test Artist",
                    Title = "Signal Fire",
                    Album = "Test Album",
                    Lead = true,
                    DownloadLink = "https://example.test/song"
                )

            let! created = writer.CreateAsync(song, CancellationToken.None)

            let filter = SongSearchFilter(Lead = Nullable(true))
            let! filtered = reader.SearchAsync(filter, 1, 10, CancellationToken.None)
            Assert.Equal(1, filtered.TotalCount)
            Assert.True(filtered.Items.[0].Lead)

            let updateTask =
                task {
                    created.SpotifyTrackId <- "spotify-track"
                    let! _ = writer.UpdateAsync(created, CancellationToken.None)
                    return ()
                }

            let readTask =
                task {
                    let! results = reader.FullTextSearchAsync("Signal", 10, CancellationToken.None)
                    Assert.Single(results) |> ignore
                }

            do! Task.WhenAll([| updateTask :> Task; readTask :> Task |])

            use requiredProvider = createProvider databasePath true
            do! requiredProvider.InitializeDatabaseAsync()
        finally
            deleteTempDirectory directory
    }

[<Fact>]
let ``search retries a transient SQLite connection failure`` () =
    task {
        let directory = createTempDirectory ()

        try
            let databasePath = Path.Combine(directory, "ignite.db")
            use provider = createProvider databasePath false
            do! provider.InitializeDatabaseAsync()

            let options =
                DbContextOptionsBuilder<IgniteDbContext>()
                    .UseSqlite($"Data Source={databasePath}")
                    .AddInterceptors(FailOnceConnectionInterceptor())
                    .Options

            use context = new IgniteDbContext(options)
            let repository = SongRepository(context) :> ISongRepository
            let! results = repository.SearchAsync(SongSearchFilter(), 1, 10, CancellationToken.None)

            Assert.Empty(results.Items)
        finally
            deleteTempDirectory directory
    }

[<Fact>]
let ``production startup adds the saved playlist snapshot table to an existing database`` () =
    task {
        let directory = createTempDirectory ()

        try
            let databasePath = Path.Combine(directory, "ignite.db")

            use initialProvider = createProvider databasePath false
            do! initialProvider.InitializeDatabaseAsync()

            use connection = new SqliteConnection($"Data Source={databasePath}")
            do! connection.OpenAsync()
            use dropCommand = connection.CreateCommand()
            dropCommand.CommandText <- "DROP TABLE playlist_search_snapshots"
            do! dropCommand.ExecuteNonQueryAsync() :> Task
            do! connection.CloseAsync()

            use requiredProvider = createProvider databasePath true
            do! requiredProvider.InitializeDatabaseAsync()

            use verificationConnection = new SqliteConnection($"Data Source={databasePath}")
            do! verificationConnection.OpenAsync()
            use verificationCommand = verificationConnection.CreateCommand()

            verificationCommand.CommandText <-
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='playlist_search_snapshots'"

            let! tableCount = verificationCommand.ExecuteScalarAsync()
            Assert.Equal(1L, Convert.ToInt64(tableCount))
        finally
            deleteTempDirectory directory
    }

[<Fact>]
let ``production rejects remote missing and relative databases`` () =
    Assert.Throws<ArgumentException>(fun () ->
        DatabaseConfiguration.validateConnectionString true "libsql://example.turso.io" |> ignore)
    |> ignore

    Assert.Throws<ArgumentException>(fun () ->
        DatabaseConfiguration.validateConnectionString true "Data Source=ignite.db" |> ignore)
    |> ignore

    let missingPath = Path.Combine(Path.GetTempPath(), $"missing-ignite-{Guid.NewGuid():N}.db")

    Assert.Throws<FileNotFoundException>(fun () ->
        DatabaseConfiguration.validateConnectionString true $"Data Source={missingPath}" |> ignore)
    |> ignore

[<Fact>]
let ``production rejects corrupt database`` () =
    task {
        let directory = createTempDirectory ()

        try
            let databasePath = Path.Combine(directory, "ignite.db")
            File.WriteAllText(databasePath, "not a sqlite database")
            use provider = createProvider databasePath true

            let! _ =
                Assert.ThrowsAsync<AggregateException>(fun () -> provider.InitializeDatabaseAsync())

            return ()
        finally
            deleteTempDirectory directory
    }

[<Fact>]
let ``production rejects database missing FTS objects`` () =
    task {
        let directory = createTempDirectory ()

        try
            let databasePath = Path.Combine(directory, "ignite.db")
            do! createBareSchemaAsync databasePath
            use provider = createProvider databasePath true

            let! error =
                Assert.ThrowsAsync<AggregateException>(fun () -> provider.InitializeDatabaseAsync())

            Assert.Contains("songs_fts", error.InnerException.Message)
        finally
            deleteTempDirectory directory
    }
