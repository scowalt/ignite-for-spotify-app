module Ignite.Infrastructure.Tests.MigrationProcessFixture

open System
open System.IO
open System.Threading
open Ignite.Infrastructure.Data

[<EntryPoint>]
let main arguments =
    match arguments with
    | [| "hold-migration"; path; ready |] ->
        DatabaseMigrations.runObserved
            path
            UpgradeExisting
            (DatabaseMigrationTests.interruptionCatalogue ())
            TimeProvider.System
            (fun identifier ->
                if identifier = "0002_change.sql" then
                    File.WriteAllText(ready, "uncommitted")
                    Thread.Sleep(Timeout.Infinite))
        |> ignore

        0
    | _ -> 2
