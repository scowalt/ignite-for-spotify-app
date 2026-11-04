module Ignite.Infrastructure.Tests.MigrationDeliveryTests

open System
open System.IO
open Ignite.Infrastructure.Data
open Microsoft.Data.Sqlite
open Xunit

let private withDatabase action =
    let directory =
        Path.Combine(Path.GetTempPath(), $"ignite-delivery-migrations-{Guid.NewGuid():N}")

    Directory.CreateDirectory(directory) |> ignore

    try
        action (Path.Combine(directory, "application.db"))
    finally
        Directory.Delete(directory, true)

let private initial =
    { Id = "0001_initial.sql"
      Sql = "CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT);\n" }

[<Fact>]
let ``automatic migrations cannot rewrite existing application data`` () =
    withDatabase (fun path ->
        let seeded =
            { initial with
                Sql = initial.Sql + "INSERT INTO sample VALUES (1, 'retained');\n" }

        DatabaseMigrations.run path CreateNew [ seeded ] |> ignore
        let before = DatabaseMigrations.inspect path

        let change =
            { Id = "0002_rewrite.sql"
              Sql = "UPDATE sample SET value = 'replaced';\n" }

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.run path (AutomaticUpgrade(before, 1024L * 1024L)) [ seeded; change ]
            |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT value FROM sample WHERE id = 1"
        Assert.Equal("retained", command.ExecuteScalar() :?> string))

[<Fact>]
let ``automatic migration requires the exact previously reviewed schema and history`` () =
    withDatabase (fun path ->
        DatabaseMigrations.run path CreateNew [ initial ] |> ignore
        let stale = DatabaseMigrations.inspect path

        let intervening =
            { Id = "0002_intervening.sql"
              Sql = "CREATE TABLE intervening (id INTEGER);\n" }

        DatabaseMigrations.run path UpgradeExisting [ initial; intervening ] |> ignore
        let before = DatabaseMigrations.inspect path

        let pending =
            { Id = "0003_pending.sql"
              Sql = "CREATE TABLE pending (id INTEGER);\n" }

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.run path (AutomaticUpgrade(stale, 1024L * 1024L)) [ initial; intervening; pending ]
            |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path))

[<Theory>]
[<InlineData("ALTER TABLE sample DROP COLUMN value;")>]
[<InlineData("ALTER TABLE sample RENAME COLUMN value TO renamed;")>]
[<InlineData("ALTER TABLE sample RENAME TO renamed;")>]
[<InlineData("ALTER TABLE sample DROP COLUMN value; ALTER TABLE sample ADD COLUMN value TEXT;")>]
[<InlineData("DROP INDEX ix_original;")>]
[<InlineData("CREATE UNIQUE INDEX ix_new ON sample(value);")>]
[<InlineData("CREATE INDEX ix_new ON sample(length(value));")>]
[<InlineData("CREATE INDEX ix_new ON sample(value) WHERE value IS NOT NULL;")>]
[<InlineData("ALTER TABLE sample ADD COLUMN note TEXT CHECK(value <> 'forbidden');")>]
[<InlineData("CREATE TRIGGER changed AFTER INSERT ON sample BEGIN SELECT 1; END;")>]
let ``automatic delivery refuses changes outside structural expansion`` sql =
    withDatabase (fun path ->
        let seeded =
            { initial with
                Sql =
                    initial.Sql
                    + "CREATE INDEX ix_original ON sample(id); INSERT INTO sample VALUES (1, 'retained');\n" }

        DatabaseMigrations.run path CreateNew [ seeded ] |> ignore
        let before = DatabaseMigrations.inspect path

        let change =
            { Id = "0002_change.sql"
              Sql = sql + "\n" }

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.run path (AutomaticUpgrade(before, 1024L * 1024L)) [ seeded; change ]
            |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT value FROM sample WHERE id = 1"
        Assert.Equal("retained", command.ExecuteScalar() :?> string))

[<Theory>]
[<InlineData("ALTER TABLE sample ADD COLUMN note TEXT;")>]
[<InlineData("ALTER TABLE sample ADD COLUMN note TEXT DEFAULT null;")>]
[<InlineData("CREATE TABLE additional (id INTEGER PRIMARY KEY, value TEXT);")>]
[<InlineData("CREATE INDEX ix_new ON sample(value);")>]
let ``automatic structural expansion preserves prior rows and records the migration`` sql =
    withDatabase (fun path ->
        let seeded =
            { initial with
                Sql = initial.Sql + "INSERT INTO sample VALUES (1, 'retained');\n" }

        DatabaseMigrations.run path CreateNew [ seeded ] |> ignore
        let before = DatabaseMigrations.inspect path

        let change =
            { Id = "0002_change.sql"
              Sql = sql + "\n" }

        let result =
            DatabaseMigrations.run path (AutomaticUpgrade(before, 1024L * 1024L)) [ seeded; change ]

        Assert.Equal<string list>([ change.Id ], result.Applied)
        Assert.Equal(2, result.History.Length)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "SELECT value FROM sample WHERE id = 1"
        Assert.Equal("retained", command.ExecuteScalar() :?> string))

[<Fact>]
let ``automatic expansion cannot exceed its explicit database budget`` () =
    withDatabase (fun path ->
        let seeded =
            { initial with
                Sql = initial.Sql + "INSERT INTO sample VALUES (1, hex(zeroblob(100000)));\n" }

        DatabaseMigrations.run path CreateNew [ seeded ] |> ignore
        let before = DatabaseMigrations.inspect path

        let small =
            { Id = "0002_small.sql"
              Sql = "CREATE TABLE first (id INTEGER);\n" }

        let large =
            { Id = "0003_large.sql"
              Sql = "CREATE INDEX large_one ON sample(value); CREATE INDEX large_two ON sample(value);\n" }

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.run path (AutomaticUpgrade(before, 384L * 1024L)) [ seeded; small; large ]
            |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path)

        use connection =
            new SqliteConnection($"Data Source={path};Mode=ReadOnly;Pooling=False")

        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "PRAGMA max_page_count"
        Assert.True((command.ExecuteScalar() :?> int64) > 384L * 1024L / 4096L))

[<Fact>]
let ``automatic expansion works with the complete application schema and existing FTS and sequences`` () =
    withDatabase (fun path ->
        let catalogue = ApplicationMigrations.catalogue ()
        DatabaseMigrations.run path CreateNew catalogue |> ignore
        use connection = new SqliteConnection($"Data Source={path};Pooling=False")
        connection.Open()
        use command = connection.CreateCommand()

        command.CommandText <-
            "INSERT INTO user_sessions (id, spotify_refresh_token, created_at, updated_at) VALUES ('fixture', 'fixture-token', '2026-01-01', '2026-01-01'); INSERT INTO scraping_jobs(job_type, status, songs_processed, songs_added, songs_updated, created_at) VALUES ('CdlcFull', 'Completed', 0, 0, 0, '2026-01-01');"

        command.ExecuteNonQuery() |> ignore
        connection.Close()
        let before = DatabaseMigrations.inspect path

        let change =
            { Id = "0002_session_note.sql"
              Sql =
                "ALTER TABLE user_sessions ADD COLUMN note TEXT; CREATE INDEX ix_job_status ON scraping_jobs(status);\n" }

        Assert.Equal<string list>(
            [ change.Id ],
            (DatabaseMigrations.run path (AutomaticUpgrade(before, 1024L * 1024L)) (catalogue @ [ change ])).Applied
        )

        connection.Open()
        command.CommandText <- "SELECT spotify_refresh_token FROM user_sessions WHERE id = 'fixture'"
        Assert.Equal("fixture-token", command.ExecuteScalar() :?> string)
        command.CommandText <- "SELECT seq FROM sqlite_sequence WHERE name = 'scraping_jobs'"
        Assert.Equal(1L, command.ExecuteScalar() :?> int64))

[<Fact>]
let ``automatic row verification handles SQLite value types and without rowid tables`` () =
    withDatabase (fun path ->
        let schema =
            { initial with
                Sql =
                    "CREATE TABLE sample (id TEXT PRIMARY KEY, label TEXT, contents BLOB, amount REAL, optional TEXT) WITHOUT ROWID; INSERT INTO sample VALUES ('fixture', CAST(x'FF' AS TEXT), x'0001FF', 1.125, NULL);\n" }

        DatabaseMigrations.run path CreateNew [ schema ] |> ignore
        let before = DatabaseMigrations.inspect path

        let change =
            { Id = "0002_note.sql"
              Sql = "ALTER TABLE sample ADD COLUMN note TEXT;\n" }

        Assert.Equal<string list>(
            [ change.Id ],
            (DatabaseMigrations.run path (AutomaticUpgrade(before, 1024L * 1024L)) [ schema; change ]).Applied
        ))

[<Fact>]
let ``a signed target schema mismatch is rejected before any migration commits`` () =
    withDatabase (fun path ->
        DatabaseMigrations.run path CreateNew [ initial ] |> ignore
        let before = DatabaseMigrations.inspect path

        let change =
            { Id = "0002_note.sql"
              Sql = "ALTER TABLE sample ADD COLUMN note TEXT;\n" }

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.run path (VerifiedUpgrade(before, String('0', 64), 1024L * 1024L)) [ initial; change ]
            |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path))

[<Fact>]
let ``production readiness refuses pending migrations without applying them`` () =
    withDatabase (fun path ->
        DatabaseMigrations.run path CreateNew [ initial ] |> ignore
        let before = DatabaseMigrations.inspect path
        DatabaseMigrations.requireReady path [ initial ] before.SchemaSha256

        let pending =
            { Id = "0002_later.sql"
              Sql = "CREATE TABLE later (id INTEGER);\n" }

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseMigrations.requireReady path [ initial; pending ] before.SchemaSha256)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path))

[<Fact>]
let ``production readiness refuses schema drift even with matching migration history`` () =
    withDatabase (fun path ->
        DatabaseMigrations.run path CreateNew [ initial ] |> ignore
        let expectedSchema = (DatabaseMigrations.inspect path).SchemaSha256
        use connection = new SqliteConnection($"Data Source={path};Pooling=False")
        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "DROP TABLE sample"
        command.ExecuteNonQuery() |> ignore
        connection.Close()

        Assert.Throws<MigrationRejected>(fun () -> DatabaseMigrations.requireReady path [ initial ] expectedSchema)
        |> ignore)
