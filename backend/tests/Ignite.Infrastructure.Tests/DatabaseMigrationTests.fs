module Ignite.Infrastructure.Tests.DatabaseMigrationTests

open System
open System.IO
open System.Threading
open System.Threading.Tasks
open System.Diagnostics
open System.Reflection
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure
open Ignite.Infrastructure.Data
open Microsoft.Extensions.Configuration
open Microsoft.Extensions.DependencyInjection
open Microsoft.Data.Sqlite
open Xunit

let private withDatabase action =
    let directory =
        Path.Combine(Path.GetTempPath(), $"ignite-migrations-{Guid.NewGuid():N}")

    Directory.CreateDirectory(directory) |> ignore

    try
        action (Path.Combine(directory, "application.db"))
    finally
        Directory.Delete(directory, true)

let private createProvider path =
    let services = ServiceCollection()

    services.AddInfrastructure(ConfigurationBuilder().Build(), $"Data Source={path}", true)
    |> ignore

    services.BuildServiceProvider()

let private initial =
    { Id = "0001_initial.sql"
      Sql = "CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL);\n" }

[<Fact>]
let ``the initial draft reproduces the reviewed production schema fingerprint`` () =
    withDatabase (fun path ->
        DatabaseMigrations.run path CreateNew [ (ApplicationMigrations.catalogue ()).Head ]
        |> ignore

        Assert.Equal(
            "91520ea3d23a8c812dea171d9bf5194e5f896069b3b540ffbab723e7b2ffa6a5",
            (DatabaseMigrations.inspect path).SchemaSha256
        ))

[<Fact>]
let ``the embedded application catalogue supports unchanged repositories and FTS`` () =
    withDatabase (fun path ->
        let catalogue = ApplicationMigrations.catalogue ()
        let report = DatabaseMigrations.run path CreateNew catalogue
        Assert.Equal<string list>(catalogue |> List.map _.Id, report.Applied)
        use provider = createProvider path
        use scope = provider.CreateScope()
        let songs = scope.ServiceProvider.GetRequiredService<ISongRepository>()

        let song =
            Song(
                Artist = "Test Artist",
                Title = "Signal Fire",
                Album = "Test Album",
                DownloadLink = "https://example.test/song"
            )

        let created =
            songs.CreateAsync(song, CancellationToken.None).GetAwaiter().GetResult()

        let matches =
            songs.FullTextSearchAsync("Signal", 10, CancellationToken.None).GetAwaiter().GetResult()

        Assert.Equal(created.Id, Assert.Single(matches).Id)
        created.Title <- "Changed Title"

        songs.UpdateAsync(created, CancellationToken.None).GetAwaiter().GetResult()
        |> ignore

        Assert.Empty(songs.FullTextSearchAsync("Signal", 10, CancellationToken.None).GetAwaiter().GetResult())

        Assert.Single(songs.FullTextSearchAsync("Changed", 10, CancellationToken.None).GetAwaiter().GetResult())
        |> ignore)

[<Fact>]
let ``explicit adoption validates the legacy schema and preserves repository data and FTS`` () =
    withDatabase (fun path ->
        LegacySchema.create path
        LegacySchema.seed path
        let before = DatabaseMigrations.inspect path
        Assert.Equal("91520ea3d23a8c812dea171d9bf5194e5f896069b3b540ffbab723e7b2ffa6a5", before.SchemaSha256)
        Assert.True(before.History.IsNone)
        let catalogue = ApplicationMigrations.catalogue ()

        let adopted =
            DatabaseMigrations.run path (AdoptLegacy before.SchemaSha256) [ catalogue.Head ]

        Assert.Empty(adopted.Applied)
        Assert.Equal("0001_initial.sql", Assert.Single(adopted.History).Id)
        let after = DatabaseMigrations.inspect path
        Assert.Equal(before.SchemaSha256, after.SchemaSha256)
        Assert.Equal<MigrationEntry list>(adopted.History, after.History.Value)
        DatabaseMigrations.run path UpgradeExisting catalogue |> ignore
        use provider = createProvider path
        use scope = provider.CreateScope()
        let songs = scope.ServiceProvider.GetRequiredService<ISongRepository>()

        Assert.Equal(
            1,
            Assert.Single(songs.FullTextSearchAsync("Signal", 10, CancellationToken.None).GetAwaiter().GetResult()).Id
        )

        Assert.Empty((DatabaseMigrations.run path UpgradeExisting catalogue).Applied))

[<Theory>]
[<InlineData("wrong-fingerprint")>]
[<InlineData("missing-fts-trigger")>]
[<InlineData("extra-table")>]
[<InlineData("pending-script")>]
[<InlineData("changed-default")>]
let ``legacy adoption refuses unreviewed schemas and cannot mark pending migrations as applied`` change =
    withDatabase (fun path ->
        LegacySchema.create path

        if
            change = "missing-fts-trigger"
            || change = "extra-table"
            || change = "changed-default"
        then
            use connection = new SqliteConnection($"Data Source={path};Pooling=False")
            connection.Open()
            use command = connection.CreateCommand()

            command.CommandText <-
                if change = "extra-table" then
                    "CREATE TABLE unknown (id INTEGER)"
                elif change = "changed-default" then
                    "ALTER TABLE songs DROP COLUMN official_dlc; ALTER TABLE songs ADD COLUMN official_dlc INTEGER NOT NULL DEFAULT 1"
                else
                    "DROP TRIGGER songs_au"

            command.ExecuteNonQuery() |> ignore

        let before = DatabaseMigrations.inspect path

        let expected =
            if change = "wrong-fingerprint" then
                String('0', 64)
            else
                before.SchemaSha256

        let catalogue = [ (ApplicationMigrations.catalogue ()).Head ]

        let scripts =
            if change = "pending-script" then
                catalogue
                @ [ { Id = "0002_pending.sql"
                      Sql = "SELECT 1;\n" } ]
            else
                catalogue

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.run path (AdoptLegacy expected) scripts |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path))

[<Fact>]
let ``adoption cannot pretend a data-changing baseline has already executed`` () =
    withDatabase (fun path ->
        use connection = new SqliteConnection($"Data Source={path};Pooling=False")
        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- initial.Sql
        command.ExecuteNonQuery() |> ignore
        connection.Close()
        let before = DatabaseMigrations.inspect path

        let seeded =
            { initial with
                Sql = initial.Sql + "INSERT INTO sample VALUES (1, 'seed');\n" }

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.run path (AdoptLegacy before.SchemaSha256) [ seeded ]
            |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path))

[<Fact>]
let ``fresh initialization journals a migration and repeat startup does not rerun it`` () =
    withDatabase (fun path ->
        let first = DatabaseMigrations.run path CreateNew [ initial ]
        Assert.Equal<string list>([ initial.Id ], first.Applied)
        Assert.Equal(initial.Id, Assert.Single(first.History).Id)
        Assert.Matches("^[a-f0-9]{64}$", first.History.Head.Sha256)
        Assert.Equal(TimeSpan.Zero, first.History.Head.AppliedAt.Offset)
        let repeated = DatabaseMigrations.run path UpgradeExisting [ initial ]
        Assert.Empty(repeated.Applied)
        Assert.Equal<MigrationEntry list>(first.History, repeated.History))

[<Theory>]
[<InlineData("edited")>]
[<InlineData("missing")>]
[<InlineData("inserted-before")>]
[<InlineData("reordered")>]
let ``history must remain an identical ordered prefix even without pending work`` change =
    withDatabase (fun path ->
        let later =
            { Id = "0003_later.sql"
              Sql = "CREATE TABLE later (id INTEGER);\n" }

        let original = [ initial; later ]
        let before = DatabaseMigrations.run path CreateNew original

        let changed =
            match change with
            | "edited" ->
                [ { initial with
                      Sql = initial.Sql + "\n" }
                  later ]
            | "missing" -> [ initial ]
            | "inserted-before" ->
                [ initial
                  { Id = "0002_inserted.sql"
                    Sql = "SELECT 1;\n" }
                  later ]
            | _ -> [ later; initial ]

        Assert.Throws<MigrationRejected>(fun () -> DatabaseMigrations.run path UpgradeExisting changed |> ignore)
        |> ignore

        let after = DatabaseMigrations.run path UpgradeExisting original
        Assert.Equal<MigrationEntry list>(before.History, after.History)
        Assert.Empty(after.Applied))

[<Theory>]
[<InlineData("empty")>]
[<InlineData("duplicate")>]
[<InlineData("duplicate-number")>]
[<InlineData("invalid-id")>]
[<InlineData("newline-id")>]
[<InlineData("nul")>]
[<InlineData("crlf")>]
[<InlineData("bom")>]
[<InlineData("invalid-utf8")>]
[<InlineData("oversized-total")>]
let ``invalid catalogues are rejected before creating a database`` change =
    withDatabase (fun path ->
        let scripts =
            match change with
            | "empty" -> []
            | "oversized-total" ->
                [ for number in 1..17 do
                      yield
                          { Id = $"{number:D4}_large.sql"
                            Sql = "SELECT 1;\n" + String(' ', 1024 * 1024 - 10) } ]
            | "duplicate" -> [ initial; initial ]
            | "duplicate-number" -> [ initial; { initial with Id = "0001_other.sql" } ]
            | "invalid-id" -> [ { initial with Id = "../initial.sql" } ]
            | "newline-id" ->
                [ { initial with
                      Id = "0001_initial.sql\n" } ]
            | "nul" ->
                [ { initial with
                      Sql = "SELECT 1;\u0000SELECT 2;\n" } ]
            | "crlf" -> [ { initial with Sql = "SELECT 1;\r\n" } ]
            | "bom" ->
                [ { initial with
                      Sql = "\uFEFFSELECT 1;\n" } ]
            | _ ->
                [ { initial with
                      Sql = "SELECT '" + String([| char 0xD800 |]) + "';\n" } ]

        Assert.Throws<MigrationRejected>(fun () -> DatabaseMigrations.run path CreateNew scripts |> ignore)
        |> ignore

        Assert.False(File.Exists(path)))

[<Theory>]
[<InlineData("create-existing")>]
[<InlineData("upgrade-untracked")>]
[<InlineData("upgrade-missing")>]
let ``normal initialization never adopts an unknown database or creates missing production data`` mode =
    withDatabase (fun path ->
        if mode <> "upgrade-missing" then
            use connection = new SqliteConnection($"Data Source={path};Pooling=False")
            connection.Open()
            use command = connection.CreateCommand()
            command.CommandText <- "CREATE TABLE legacy_data (id INTEGER);"
            command.ExecuteNonQuery() |> ignore

        let request =
            if mode = "create-existing" then
                CreateNew
            else
                UpgradeExisting

        Assert.Throws<MigrationRejected>(fun () -> DatabaseMigrations.run path request [ initial ] |> ignore)
        |> ignore

        if mode = "upgrade-missing" then
            Assert.False(File.Exists(path))
        else
            use connection =
                new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

            connection.Open()
            use command = connection.CreateCommand()
            command.CommandText <- "SELECT count(*) FROM sqlite_schema WHERE name = '__ignite_migrations'"
            Assert.Equal(0L, command.ExecuteScalar() :?> int64))

[<Theory>]
[<InlineData("SELECT missing_private_value FROM missing_table;")>]
[<InlineData("COMMIT; SELECT missing_private_value FROM missing_table;")>]
[<InlineData("UPDATE __ignite_migrations SET applied_at = '2000-01-01T00:00:00+00:00';")>]
[<InlineData("ATTACH DATABASE ':memory:' AS escaped;")>]
[<InlineData("PRAGMA user_version = 13;")>]
[<InlineData("SAVEPOINT escaped; RELEASE escaped;")>]
let ``failed or transaction escaping scripts cannot preserve earlier batch changes`` sql =
    withDatabase (fun path ->
        let before = DatabaseMigrations.run path CreateNew [ initial ]

        let change =
            { Id = "0002_change.sql"
              Sql = "INSERT INTO sample VALUES (1, 'private-marker'); CREATE TABLE added (id INTEGER);\n" }

        let failure =
            { Id = "0003_failure.sql"
              Sql = sql + "\n" }

        let error =
            Assert.Throws<MigrationRejected>(fun () ->
                DatabaseMigrations.run path UpgradeExisting [ initial; change; failure ]
                |> ignore)

        Assert.DoesNotContain("private", error.ToString())
        Assert.Null(error.InnerException)
        let after = DatabaseMigrations.run path UpgradeExisting [ initial ]
        Assert.Equal<MigrationEntry list>(before.History, after.History)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT count(*) FROM sample"
        Assert.Equal(0L, command.ExecuteScalar() :?> int64)
        command.CommandText <- "SELECT count(*) FROM sqlite_schema WHERE name = 'added'"
        Assert.Equal(0L, command.ExecuteScalar() :?> int64))

[<Theory>]
[<InlineData("DELETE FROM __ignite_migrations")>]
[<InlineData("UPDATE __ignite_migrations SET position = 2")>]
[<InlineData("UPDATE __ignite_migrations SET applied_at = '2099-01-01T00:00:00.0000000+00:00'")>]
[<InlineData("CREATE TRIGGER journal_rewrite AFTER INSERT ON __ignite_migrations BEGIN SELECT 1; END")>]
let ``corrupt journal metadata is rejected even on a no-op startup`` sql =
    withDatabase (fun path ->
        let noop = { initial with Sql = "SELECT 1;\n" }
        DatabaseMigrations.run path CreateNew [ noop ] |> ignore
        use connection = new SqliteConnection($"Data Source={path};Pooling=False")
        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- sql
        command.ExecuteNonQuery() |> ignore
        connection.Close()

        Assert.Throws<MigrationRejected>(fun () -> DatabaseMigrations.run path UpgradeExisting [ noop ] |> ignore)
        |> ignore

        Assert.Throws<MigrationRejected>(fun () -> DatabaseMigrations.inspect path |> ignore)
        |> ignore)

[<Fact>]
let ``migration and inspection refuse a symbolic link to another database`` () =
    withDatabase (fun path ->
        let before = DatabaseMigrations.run path CreateNew [ initial ]
        let link = path + ".link"
        File.CreateSymbolicLink(link, path) |> ignore

        let change =
            { Id = "0002_change.sql"
              Sql = "CREATE TABLE added (id INTEGER);\n" }

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.run link UpgradeExisting [ initial; change ] |> ignore)
        |> ignore

        Assert.Throws<MigrationRejected>(fun () -> DatabaseMigrations.inspect link |> ignore)
        |> ignore

        Assert.Equal<MigrationEntry list>(
            before.History,
            (DatabaseMigrations.run path UpgradeExisting [ initial ]).History
        ))

[<Fact>]
let ``SQL literals are not substituted or mistaken for transaction commands`` () =
    withDatabase (fun path ->
        DatabaseMigrations.run path CreateNew [ initial ] |> ignore

        let change =
            { Id = "0002_literal.sql"
              Sql = "INSERT INTO sample VALUES (1, '$schema$ $variable$ COMMIT;');\n" }

        Assert.Equal<string list>(
            [ change.Id ],
            (DatabaseMigrations.run path UpgradeExisting [ initial; change ]).Applied
        )

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT value FROM sample WHERE id = 1"
        Assert.Equal("$schema$ $variable$ COMMIT;", command.ExecuteScalar() :?> string))

[<Fact>]
let ``commit failure restores the prior database after every script and journal entry ran`` () =
    withDatabase (fun path ->
        let before = DatabaseMigrations.run path CreateNew [ initial ]

        let change =
            { Id = "0002_foreign_key.sql"
              Sql =
                "CREATE TABLE parent (id INTEGER PRIMARY KEY); CREATE TABLE child (id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED); INSERT INTO child VALUES (42);\n" }

        let observed = ResizeArray<string>()

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.runObserved path UpgradeExisting [ initial; change ] TimeProvider.System observed.Add
            |> ignore)
        |> ignore

        Assert.Equal<string list>([ change.Id ], List.ofSeq observed)
        let after = DatabaseMigrations.run path UpgradeExisting [ initial ]
        Assert.Equal<MigrationEntry list>(before.History, after.History)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT count(*) FROM sqlite_schema WHERE name IN ('parent', 'child')"
        Assert.Equal(0L, command.ExecuteScalar() :?> int64))

[<Theory>]
[<InlineData(false)>]
[<InlineData(true)>]
let ``fresh and adopted databases preserve sessions snapshots and job records`` adopt =
    withDatabase (fun path ->
        let catalogue = ApplicationMigrations.catalogue ()

        if adopt then
            LegacySchema.create path
            LegacySchema.seed path

            DatabaseMigrations.run path (AdoptLegacy (DatabaseMigrations.inspect path).SchemaSha256) [ catalogue.Head ]
            |> ignore

            DatabaseMigrations.run path UpgradeExisting catalogue |> ignore
        else
            DatabaseMigrations.run path CreateNew catalogue |> ignore

        use provider = createProvider path

        let sessionId =
            if adopt then
                "session_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            else
                UserSessionId.create ()

        let jobId =
            if adopt then
                1
            else
                use scope = provider.CreateScope()
                let sessions = scope.ServiceProvider.GetRequiredService<IUserSessionRepository>()

                let snapshots =
                    scope.ServiceProvider.GetRequiredService<IPlaylistSearchSnapshotRepository>()

                let jobs = scope.ServiceProvider.GetRequiredService<IScrapingJobRepository>()

                sessions
                    .CreateAsync(
                        UserSession(
                            Id = sessionId,
                            SpotifyUserId = "fixture-user",
                            SpotifyAccessToken = "fixture-access",
                            SpotifyRefreshToken = "fixture-refresh"
                        ),
                        CancellationToken.None
                    )
                    .GetAwaiter()
                    .GetResult()
                |> ignore

                snapshots
                    .UpsertAsync(
                        PlaylistSearchSnapshot(
                            SpotifyUserId = "fixture-user",
                            PlaylistId = "fixture-playlist",
                            ResultsJson = "[]",
                            TotalTracks = 12
                        ),
                        CancellationToken.None
                    )
                    .GetAwaiter()
                    .GetResult()
                |> ignore

                jobs
                    .CreateAsync(
                        ScrapingJob(
                            JobType = ScrapingJobType.CdlcIncremental,
                            Status = ScrapingJobStatus.Completed,
                            HangfireJobId = "fixture-job"
                        ),
                        CancellationToken.None
                    )
                    .GetAwaiter()
                    .GetResult()
                    .Id

        use readScope = provider.CreateScope()

        let sessions =
            readScope.ServiceProvider.GetRequiredService<IUserSessionRepository>()

        let snapshots =
            readScope.ServiceProvider.GetRequiredService<IPlaylistSearchSnapshotRepository>()

        let jobs = readScope.ServiceProvider.GetRequiredService<IScrapingJobRepository>()

        let session =
            sessions.GetByIdAsync(sessionId, CancellationToken.None).GetAwaiter().GetResult()

        Assert.Equal("fixture-access", session.SpotifyAccessToken)
        Assert.Equal("fixture-refresh", session.SpotifyRefreshToken)
        Assert.Equal("fixture-user", session.SpotifyUserId)

        Assert.Equal(
            12,
            snapshots
                .GetLatestAsync("fixture-user", "fixture-playlist", CancellationToken.None)
                .GetAwaiter()
                .GetResult()
                .TotalTracks
        )

        Assert.Null(
            snapshots.GetLatestAsync("other-user", "fixture-playlist", CancellationToken.None).GetAwaiter().GetResult()
        )

        let job = jobs.GetByIdAsync(jobId, CancellationToken.None).GetAwaiter().GetResult()
        Assert.Equal("fixture-job", job.HangfireJobId)
        Assert.Equal(ScrapingJobStatus.Completed, job.Status))

type JournalFailureClock() =
    inherit TimeProvider()
    let mutable entries = 0

    override _.GetUtcNow() =
        entries <- entries + 1

        if entries = 2 then
            failwith "private journal clock failure"

        DateTimeOffset.UtcNow

[<Fact>]
let ``journal insertion failure rolls back preceding scripts and their history`` () =
    withDatabase (fun path ->
        let before = DatabaseMigrations.run path CreateNew [ initial ]

        let change =
            { Id = "0002_change.sql"
              Sql = "INSERT INTO sample VALUES (1, 'private-marker');\n" }

        let later =
            { Id = "0003_later.sql"
              Sql = "CREATE TABLE added (id INTEGER);\n" }

        let observed = ResizeArray<string>()

        let error =
            Assert.Throws<MigrationRejected>(fun () ->
                DatabaseMigrations.runObserved
                    path
                    UpgradeExisting
                    [ initial; change; later ]
                    (JournalFailureClock())
                    observed.Add
                |> ignore)

        Assert.Equal<string list>([ change.Id ], List.ofSeq observed)
        Assert.DoesNotContain("private journal clock failure", error.ToString())
        let after = DatabaseMigrations.run path UpgradeExisting [ initial ]
        Assert.Equal<MigrationEntry list>(before.History, after.History)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT count(*) FROM sample"
        Assert.Equal(0L, command.ExecuteScalar() :?> int64)
        command.CommandText <- "SELECT count(*) FROM sqlite_schema WHERE name = 'added'"
        Assert.Equal(0L, command.ExecuteScalar() :?> int64))

let interruptionCatalogue () =
    [ initial
      { Id = "0002_change.sql"
        Sql = "INSERT INTO sample VALUES (1, 'private-marker'); CREATE TABLE added (id INTEGER);\n" } ]

let interruptionCatalogueWithSpill () =
    [ initial
      { Id = "0002_change.sql"
        Sql = "INSERT INTO sample VALUES (1, hex(zeroblob(3000000))); CREATE TABLE added (id INTEGER);\n" } ]

[<Fact>]
let ``concurrent migration attempts cannot enter the same pending batch`` () =
    withDatabase (fun path ->
        DatabaseMigrations.run path CreateNew [ initial ] |> ignore
        use ready = new ManualResetEventSlim()
        use release = new ManualResetEventSlim()

        let completed =
            TaskCompletionSource<MigrationReport>(TaskCreationOptions.RunContinuationsAsynchronously)

        let worker =
            new Thread(
                ThreadStart(fun () ->
                    try
                        let report =
                            DatabaseMigrations.runObserved
                                path
                                UpgradeExisting
                                (interruptionCatalogue ())
                                TimeProvider.System
                                (fun _ ->
                                    ready.Set()

                                    if not (release.Wait(TimeSpan.FromSeconds(15.0))) then
                                        failwith "fixture_timeout")

                        completed.SetResult(report)
                    with error ->
                        completed.SetException(error))
            )

        worker.IsBackground <- true
        worker.Start()

        try
            Assert.True(ready.Wait(TimeSpan.FromSeconds(10.0)))

            Assert.Throws<MigrationRejected>(fun () ->
                DatabaseMigrations.run path UpgradeExisting (interruptionCatalogue ()) |> ignore)
            |> ignore
        finally
            release.Set()
            Assert.True(worker.Join(TimeSpan.FromSeconds(10.0)))

        Assert.Equal<string list>([ "0002_change.sql" ], completed.Task.GetAwaiter().GetResult().Applied)
        Assert.Empty((DatabaseMigrations.run path UpgradeExisting (interruptionCatalogue ())).Applied))

[<Fact>]
let ``killing a migration process rolls back schema data and history before restart`` () =
    withDatabase (fun path ->
        let before = DatabaseMigrations.run path CreateNew [ initial ]
        let ready = path + ".ready"

        let start =
            ProcessStartInfo(
                "dotnet",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false
            )

        for argument in [ Assembly.GetExecutingAssembly().Location; "hold-migration"; path; ready ] do
            start.ArgumentList.Add(argument)

        use child = Process.Start(start) |> nonNull

        try
            let deadline = DateTime.UtcNow.AddSeconds(15)

            while not (File.Exists(ready)) && not child.HasExited && DateTime.UtcNow < deadline do
                Thread.Sleep(10)

            Assert.True(File.Exists(ready), "The child must reach an uncommitted completed script before termination.")
        finally
            if not child.HasExited then
                child.Kill(entireProcessTree = true)

            Assert.True(child.WaitForExit(10000))

        let after = DatabaseMigrations.run path UpgradeExisting [ initial ]
        Assert.Equal<MigrationEntry list>(before.History, after.History)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT count(*) FROM sample"
        Assert.Equal(0L, command.ExecuteScalar() :?> int64)
        command.CommandText <- "SELECT count(*) FROM sqlite_schema WHERE name = 'added'"
        Assert.Equal(0L, command.ExecuteScalar() :?> int64))

[<Fact>]
let ``a failure outside the command callback still rolls back the entire pending batch`` () =
    withDatabase (fun path ->
        let before = DatabaseMigrations.run path CreateNew [ initial ]

        let change =
            { Id = "0002_change.sql"
              Sql = "INSERT INTO sample VALUES (1, 'private-marker');\n" }

        let afterChange =
            { Id = "0003_change.sql"
              Sql = "CREATE TABLE added (id INTEGER);\n" }

        let observed = ResizeArray<string>()

        let observer identifier =
            observed.Add(identifier)

            if identifier = afterChange.Id then
                failwith "private diagnostic value"

        let error =
            Assert.Throws<MigrationRejected>(fun () ->
                DatabaseMigrations.runObserved
                    path
                    UpgradeExisting
                    [ initial; change; afterChange ]
                    TimeProvider.System
                    observer
                |> ignore)

        Assert.Equal<string list>([ change.Id; afterChange.Id ], List.ofSeq observed)
        Assert.DoesNotContain("private diagnostic value", error.ToString())
        let after = DatabaseMigrations.run path UpgradeExisting [ initial ]
        Assert.Equal<MigrationEntry list>(before.History, after.History)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT count(*) FROM sample"
        Assert.Equal(0L, command.ExecuteScalar() :?> int64))
