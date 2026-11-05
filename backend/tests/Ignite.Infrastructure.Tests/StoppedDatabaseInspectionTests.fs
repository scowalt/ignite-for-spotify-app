module Ignite.Infrastructure.Tests.StoppedDatabaseInspectionTests

open System.IO
open Ignite.Infrastructure.Data
open Microsoft.Data.Sqlite
open Xunit

let private withDatabase action =
    let directory = Directory.CreateTempSubdirectory("ignite-stopped-inspection-")

    try
        let path = Path.Combine(directory.FullName, "frozen #? sample.db")

        DatabaseMigrations.run path CreateNew (ApplicationMigrations.catalogue ())
        |> ignore

        action path
    finally
        directory.Delete(true)

[<Fact>]
let ``stopped inspection handles escaped paths without creating WAL sidecars`` () =
    withDatabase (fun path ->
        let before = DatabaseMigrations.inspect path
        use connection = new SqliteConnection($"Data Source={path};Pooling=False")
        connection.Open()
        use command = connection.CreateCommand()
        command.CommandText <- "PRAGMA journal_mode=WAL"
        Assert.Equal("wal", command.ExecuteScalar() :?> string)
        connection.Close()
        let bytes = File.ReadAllBytes(path)
        Assert.Equal(before, DatabaseMigrations.inspectStopped path)
        Assert.True((bytes = File.ReadAllBytes(path)))

        for suffix in [ "-wal"; "-shm"; "-journal" ] do
            Assert.False(File.Exists(path + suffix)))

[<Fact>]
let ``stopped inspection does not ignore committed uncheckpointed WAL`` () =
    withDatabase (fun path ->
        let before = DatabaseMigrations.inspect path
        use connection = new SqliteConnection($"Data Source={path};Pooling=False")
        connection.Open()
        use command = connection.CreateCommand()

        command.CommandText <-
            "PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=0; CREATE TABLE wal_only (id INTEGER);"

        command.ExecuteNonQuery() |> ignore
        Assert.True(File.Exists(path + "-wal"))
        let live = DatabaseMigrations.inspect path
        let stopped = DatabaseMigrations.inspectStopped path
        Assert.NotEqual<string>(before.SchemaSha256, stopped.SchemaSha256)
        Assert.Equal(live, stopped))

[<Fact>]
let ``stopped inspection refuses dangling sidecar aliases`` () =
    withDatabase (fun path ->
        File.CreateSymbolicLink(path + "-wal", path + ".absent") |> ignore

        Assert.Throws<MigrationRejected>(fun () -> DatabaseMigrations.inspectStopped path |> ignore)
        |> ignore)
