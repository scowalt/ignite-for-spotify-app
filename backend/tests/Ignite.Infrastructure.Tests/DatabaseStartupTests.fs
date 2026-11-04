module Ignite.Infrastructure.Tests.DatabaseStartupTests

open System.IO
open Ignite.Infrastructure.Data
open Microsoft.Data.Sqlite
open Xunit

let private withDatabase action =
    let directory = Directory.CreateTempSubdirectory("ignite-startup-")

    try
        action (Path.Combine(directory.FullName, "application.db"))
    finally
        directory.Delete(true)

let private plan: MigrationCatalogue.Step list =
    [ { Script =
          { Id = "0001_initial.sql"
            Sql = "CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT);\n" }
        Delivery = MigrationCatalogue.Baseline } ]

[<Fact>]
let ``development initialization creates a journaled WAL database`` () =
    withDatabase (fun path ->
        let connectionString =
            DatabaseStartup.initialize $"Data Source={path}" false plan None

        Assert.True(File.Exists(path))
        Assert.Equal(1, (DatabaseMigrations.inspect path).History.Value.Length)
        use connection = new SqliteConnection(connectionString)
        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "PRAGMA journal_mode"
        Assert.Equal("wal", command.ExecuteScalar() :?> string)
        command.CommandText <- "PRAGMA foreign_keys"
        Assert.Equal(1L, command.ExecuteScalar() :?> int64))

[<Fact>]
let ``production startup refuses pending migrations instead of executing them`` () =
    withDatabase (fun path ->
        DatabaseMigrations.run path CreateNew (plan |> List.map _.Script) |> ignore
        let before = DatabaseMigrations.inspect path

        let upgraded =
            plan
            @ [ { Script =
                    { Id = "0002_extra.sql"
                      Sql = "CREATE TABLE extra (id INTEGER);\n" }
                  Delivery = MigrationCatalogue.AutomaticSchema } ]

        let descriptor = MigrationCatalogue.build upgraded

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseStartup.initialize $"Data Source={path}" true upgraded (Some descriptor)
            |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path))

[<Fact>]
let ``development and production cannot silently adopt an unjournaled database`` () =
    withDatabase (fun path ->
        use connection = new SqliteConnection($"Data Source={path};Pooling=False")
        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- plan.Head.Script.Sql
        command.ExecuteNonQuery() |> ignore
        connection.Close()
        let before = DatabaseMigrations.inspect path
        let descriptor = MigrationCatalogue.build plan

        for requireExisting in [ false; true ] do
            Assert.Throws<MigrationRejected>(fun () ->
                DatabaseStartup.initialize $"Data Source={path};Pooling=False" requireExisting plan (Some descriptor)
                |> ignore)
            |> ignore

            Assert.Equal(before, DatabaseMigrations.inspect path))

[<Fact>]
let ``production startup cannot initialize missing data or proceed without image metadata`` () =
    withDatabase (fun path ->
        let descriptor = MigrationCatalogue.build plan

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseStartup.initialize $"Data Source={path}" true plan (Some descriptor)
            |> ignore)
        |> ignore

        Assert.False(File.Exists(path))
        DatabaseMigrations.run path CreateNew (plan |> List.map _.Script) |> ignore
        let before = DatabaseMigrations.inspect path

        Assert.Throws<MigrationRejected>(fun () ->
            DatabaseStartup.initialize $"Data Source={path}" true plan None |> ignore)
        |> ignore

        Assert.Equal(before, DatabaseMigrations.inspect path))
