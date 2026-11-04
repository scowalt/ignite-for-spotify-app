module Ignite.MigrationWriterFixture

open System
open System.IO
open System.Text.Json
open System.Threading
open Ignite.Infrastructure.Data

[<EntryPoint>]
let main arguments =
    try
        if arguments <> [| "apply"; "/app/migration-catalogue.json" |] then
            invalidArg "arguments" "fixture_arguments"

        use input = JsonDocument.Parse(Console.In.ReadToEnd())
        let path = input.RootElement.GetProperty("database_path").GetString() |> nonNull
        let phase = input.RootElement.GetProperty("fixture_phase").GetString() |> nonNull

        if path <> "/data/ignite.db" || (phase <> "before" && phase <> "after") then
            invalidArg "input" "fixture_input"

        let hold () =
            File.WriteAllText("/data/fixture-ready", phase)
            Thread.Sleep(Timeout.Infinite)

        let pending =
            { Id = "9999_fixture.sql"
              Sql =
                "CREATE TABLE fixture_expansion (payload BLOB); INSERT INTO fixture_expansion VALUES (zeroblob(6000000));\n" }

        DatabaseMigrations.runObserved
            path
            UpgradeExisting
            (ApplicationMigrations.catalogue () @ [ pending ])
            TimeProvider.System
            (fun identifier ->
                if identifier = pending.Id && phase = "before" then
                    hold ())
        |> ignore

        hold ()
        0
    with _ ->
        1
