module Ignite.Infrastructure.Tests.MigrationCatalogueTests

open System.Text
open Ignite.Infrastructure.Data
open Xunit

let private scripts =
    [ { Id = "0001_initial.sql"
        Sql = "CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT);\n" }
      { Id = "0002_note.sql"
        Sql = "ALTER TABLE sample ADD COLUMN note TEXT;\n" } ]

let private metadata =
    Encoding.UTF8.GetBytes(
        """{"schema":1,"migrations":[{"id":"0001_initial.sql","delivery":"baseline"},{"id":"0002_note.sql","delivery":"automatic-schema"}]}"""
    )

[<Fact>]
let ``build metadata binds validated source and delivery policy with stable schema fingerprints`` () =
    let plan = MigrationCatalogue.plan scripts metadata
    Assert.Equal(2, plan.Length)
    Assert.Equal(MigrationCatalogue.AutomaticSchema, plan.[1].Delivery)
    let first = MigrationCatalogue.build plan
    let repeated = MigrationCatalogue.build plan
    Assert.Equal(first, repeated)
    Assert.Equal(2, first.Steps.Length)
    Assert.Equal("b546f0a40bfec1545cbc9f0b5e19b697967c5e43b186842d29d9ad8695d5856d", first.CatalogueSha256)
    Assert.Equal("fc2e52c16b9d7d9c943b71f73924d872a81feaebabf0ebf95fd7fe5ebff42447", first.Steps.Head.Sha256)
    Assert.Matches("^[a-f0-9]{64}$", first.SchemaSha256)
    Assert.NotEqual<string>(first.BaselineSchemaSha256, first.SchemaSha256)

[<Fact>]
let ``the embedded delivery plan describes the application baseline`` () =
    let plan = ApplicationMigrations.deliveryPlan ()
    let descriptor = MigrationCatalogue.build plan
    Assert.Equal(MigrationCatalogue.Baseline, descriptor.Steps.Head.Delivery)
    Assert.Equal("0001_initial.sql", descriptor.Steps.Head.Id)
    Assert.Equal(descriptor, MigrationCatalogue.decode plan (MigrationCatalogue.encode descriptor))

[<Fact>]
let ``runtime metadata round trips without exposing SQL and verifies its source binding`` () =
    let plan = MigrationCatalogue.plan scripts metadata
    let descriptor = MigrationCatalogue.build plan
    let encoded = MigrationCatalogue.encode descriptor
    Assert.Equal(descriptor, MigrationCatalogue.decode plan encoded)
    Assert.DoesNotContain("CREATE TABLE", Encoding.UTF8.GetString(encoded))

[<Theory>]
[<InlineData("{\"schema\":1,\"schema\":1,\"migrations\":[]}")>]
[<InlineData("{\"schema\":true,\"migrations\":[]}")>]
[<InlineData("{\"schema\":1,\"migrations\":[],\"extra\":true}")>]
[<InlineData("{\"schema\":1,\"migrations\":[{\"id\":\"0002_note.sql\",\"delivery\":\"baseline\"}]}")>]
let ``authoring metadata is strict and must describe the exact ordered catalogue`` (malformed: string) =
    Assert.Throws<MigrationRejected>(fun () ->
        MigrationCatalogue.plan scripts (Encoding.UTF8.GetBytes(malformed)) |> ignore)
    |> ignore

[<Fact>]
let ``changing SQL or delivery policy invalidates old runtime metadata`` () =
    let plan = MigrationCatalogue.plan scripts metadata
    let encoded = MigrationCatalogue.encode (MigrationCatalogue.build plan)

    let changedSql =
        [ scripts.Head
          { scripts.Tail.Head with
              Sql = "ALTER TABLE sample ADD COLUMN other TEXT;\n" } ]

    let changedPlan = MigrationCatalogue.plan changedSql metadata

    Assert.Throws<MigrationRejected>(fun () -> MigrationCatalogue.decode changedPlan encoded |> ignore)
    |> ignore

    let manualMetadata =
        Encoding.UTF8.GetBytes(Encoding.UTF8.GetString(metadata).Replace("automatic-schema", "manual"))

    let manual = MigrationCatalogue.plan scripts manualMetadata

    Assert.Throws<MigrationRejected>(fun () -> MigrationCatalogue.decode manual encoded |> ignore)
    |> ignore

    Assert.NotEqual<string>(
        (MigrationCatalogue.build plan).CatalogueSha256,
        (MigrationCatalogue.build manual).CatalogueSha256
    )

[<Fact>]
let ``automatic declaration cannot authorize data changes during the build rehearsal`` () =
    let rewrite =
        [ scripts.Head
          { scripts.Tail.Head with
              Sql = "UPDATE sample SET value = 'changed';\n" } ]

    let automatic = MigrationCatalogue.plan rewrite metadata

    Assert.Throws<MigrationRejected>(fun () -> MigrationCatalogue.build automatic |> ignore)
    |> ignore

    let manualMetadata =
        Encoding.UTF8.GetBytes(Encoding.UTF8.GetString(metadata).Replace("automatic-schema", "manual"))

    let manual = MigrationCatalogue.plan rewrite manualMetadata
    Assert.Equal(MigrationCatalogue.Manual, (MigrationCatalogue.build manual).Steps.[1].Delivery)

[<Theory>]
[<InlineData("duplicate")>]
[<InlineData("unknown")>]
[<InlineData("checksum")>]
[<InlineData("protocol")>]
let ``runtime descriptor rejects malformed identity and schema`` change =
    let plan = MigrationCatalogue.plan scripts metadata
    let descriptor = MigrationCatalogue.build plan
    let text = Encoding.UTF8.GetString(MigrationCatalogue.encode descriptor)

    let invalid =
        match change with
        | "duplicate" -> text.Replace("\"protocol\":1", "\"protocol\":1,\"protocol\":1")
        | "unknown" -> text.Replace("\"protocol\":1", "\"protocol\":1,\"extra\":true")
        | "checksum" -> text.Replace(descriptor.CatalogueSha256, System.String('0', 64))
        | _ -> text.Replace("\"protocol\":1", "\"protocol\":true")

    Assert.Throws<MigrationRejected>(fun () ->
        MigrationCatalogue.decode plan (Encoding.UTF8.GetBytes(invalid)) |> ignore)
    |> ignore
