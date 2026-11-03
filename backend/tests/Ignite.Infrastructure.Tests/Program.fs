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
    | [| "hold-large-migration"; path; ready |] ->
        DatabaseMigrations.runObserved
            path
            UpgradeExisting
            (DatabaseMigrationTests.interruptionCatalogueWithSpill ())
            TimeProvider.System
            (fun identifier ->
                if identifier = "0002_change.sql" then
                    File.WriteAllText(ready, "uncommitted")
                    Thread.Sleep(Timeout.Infinite))
        |> ignore

        0
    | arguments when arguments.Length > 0 && arguments.[0] = "migration-cli-fixture" ->
        Ignite.Migrations.Program.run MigrationCommandTests.fixturePlan (Array.skip 1 arguments)
    | arguments when arguments.Length > 0 && arguments.[0] = "migration-cli-manual-fixture" ->
        Ignite.Migrations.Program.run MigrationCommandTests.fixtureManualPlan (Array.skip 1 arguments)
    | _ -> 2
