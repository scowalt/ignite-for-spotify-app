namespace Ignite.Infrastructure.Data

open System
open System.IO
open System.Security.Cryptography
open System.Text
open System.Text.Json
open System.Text.RegularExpressions

[<RequireQualifiedAccess>]
module MigrationCatalogue =
    type Delivery =
        | Baseline
        | AutomaticSchema
        | Manual

    type Step =
        { Script: MigrationScript
          Delivery: Delivery }

    type Identity =
        { Id: string
          Sha256: string
          Delivery: Delivery }

    type Descriptor =
        { Protocol: int
          CatalogueSha256: string
          BaselineSchemaSha256: string
          SchemaSha256: string
          Steps: Identity list }

    let private reject () =
        raise (MigrationRejected("migration_catalogue_invalid"))

    let private deliveryName =
        function
        | Baseline -> "baseline"
        | AutomaticSchema -> "automatic-schema"
        | Manual -> "manual"

    let private objectKeys expected (value: JsonElement) =
        if value.ValueKind <> JsonValueKind.Object then
            reject ()

        let actual = value.EnumerateObject() |> Seq.map _.Name |> Seq.sort |> Seq.toList

        if actual <> List.sort expected then
            reject ()

    let private validatePlan (steps: Step list) =
        let scripts = steps |> List.map _.Script
        DatabaseMigrations.identifyCatalogue scripts |> ignore

        if steps.Head.Script.Id <> "0001_initial.sql" || steps.Head.Delivery <> Baseline then
            reject ()

        if steps.Tail |> List.exists (fun step -> step.Delivery = Baseline) then
            reject ()

    let plan (scripts: MigrationScript list) (metadata: byte array) : Step list =
        try
            DatabaseMigrations.identifyCatalogue scripts |> ignore

            if metadata.Length > 1024 * 1024 then
                reject ()

            use document = JsonDocument.Parse(metadata, JsonDocumentOptions(MaxDepth = 8))
            let root = document.RootElement
            objectKeys [ "schema"; "migrations" ] root

            if root.GetProperty("schema").GetInt32() <> 1 then
                reject ()

            let rows = root.GetProperty("migrations").EnumerateArray() |> Seq.toList

            if rows.Length <> scripts.Length then
                reject ()

            let steps =
                List.zip scripts rows
                |> List.map (fun (script, row) ->
                    objectKeys [ "id"; "delivery" ] row

                    if row.GetProperty("id").GetString() <> script.Id then
                        reject ()

                    let delivery =
                        match row.GetProperty("delivery").GetString() with
                        | "baseline" -> Baseline
                        | "automatic-schema" -> AutomaticSchema
                        | "manual" -> Manual
                        | _ -> reject ()

                    { Script = script; Delivery = delivery })

            validatePlan steps
            steps
        with
        | :? MigrationRejected -> reraise ()
        | _ -> reject ()

    let private identities steps =
        let source = DatabaseMigrations.identifyCatalogue (steps |> List.map _.Script)

        List.zip steps source
        |> List.map (fun (step, (id, checksum)) ->
            { Id = id
              Sha256 = checksum
              Delivery = step.Delivery })

    let private catalogueHash (steps: Identity list) =
        let text =
            "ignite-database-catalogue-v1\n"
            + (steps
               |> List.map (fun step -> step.Id + "\t" + step.Sha256 + "\t" + deliveryName step.Delivery + "\n")
               |> String.concat "")

        text |> Encoding.UTF8.GetBytes |> SHA256.HashData |> Convert.ToHexStringLower

    let private validateDescriptor (descriptor: Descriptor) =
        if
            descriptor.Protocol <> 1
            || descriptor.Steps.IsEmpty
            || descriptor.Steps.Length > 4096
        then
            reject ()

        for hash in
            [ descriptor.CatalogueSha256
              descriptor.BaselineSchemaSha256
              descriptor.SchemaSha256 ] do
            if not (Regex.IsMatch(hash, "\\A[a-f0-9]{64}\\z")) then
                reject ()

        if descriptor.CatalogueSha256 <> catalogueHash descriptor.Steps then
            reject ()

    let encode (descriptor: Descriptor) : byte array =
        try
            validateDescriptor descriptor
            use output = new MemoryStream()
            use writer = new Utf8JsonWriter(output)
            writer.WriteStartObject()
            writer.WriteNumber("protocol", descriptor.Protocol)
            writer.WriteString("catalogue_sha256", descriptor.CatalogueSha256)
            writer.WriteString("baseline_schema_sha256", descriptor.BaselineSchemaSha256)
            writer.WriteString("schema_sha256", descriptor.SchemaSha256)
            writer.WriteStartArray("migrations")

            for step in descriptor.Steps do
                writer.WriteStartObject()
                writer.WriteString("id", step.Id)
                writer.WriteString("sha256", step.Sha256)
                writer.WriteString("delivery", deliveryName step.Delivery)
                writer.WriteEndObject()

            writer.WriteEndArray()
            writer.WriteEndObject()
            writer.Flush()

            if output.Length > 1024L * 1024L then
                reject ()

            output.ToArray()
        with
        | :? MigrationRejected -> reraise ()
        | _ -> reject ()

    let decode (steps: Step list) (bytes: byte array) : Descriptor =
        try
            validatePlan steps

            if bytes.Length > 1024 * 1024 then
                reject ()

            use document = JsonDocument.Parse(bytes, JsonDocumentOptions(MaxDepth = 8))
            let root = document.RootElement

            objectKeys
                [ "protocol"
                  "catalogue_sha256"
                  "baseline_schema_sha256"
                  "schema_sha256"
                  "migrations" ]
                root

            let expected = identities steps
            let rows = root.GetProperty("migrations").EnumerateArray() |> Seq.toList

            if rows.Length <> expected.Length then
                reject ()

            for identity, row in List.zip expected rows do
                objectKeys [ "id"; "sha256"; "delivery" ] row

                if
                    row.GetProperty("id").GetString() <> identity.Id
                    || row.GetProperty("sha256").GetString() <> identity.Sha256
                    || row.GetProperty("delivery").GetString() <> deliveryName identity.Delivery
                then
                    reject ()

            let descriptor =
                { Protocol = root.GetProperty("protocol").GetInt32()
                  CatalogueSha256 = root.GetProperty("catalogue_sha256").GetString() |> nonNull
                  BaselineSchemaSha256 = root.GetProperty("baseline_schema_sha256").GetString() |> nonNull
                  SchemaSha256 = root.GetProperty("schema_sha256").GetString() |> nonNull
                  Steps = expected }

            validateDescriptor descriptor
            descriptor
        with
        | :? MigrationRejected -> reraise ()
        | _ -> reject ()

    let build (steps: Step list) : Descriptor =
        try
            validatePlan steps
            let baseline = DatabaseMigrations.baselineSchema steps.Head.Script
            let directory = Directory.CreateTempSubdirectory("ignite-catalogue-")

            try
                let path = Path.Combine(directory.FullName, "application.db")
                let mutable prefix = [ steps.Head.Script ]
                DatabaseMigrations.run path CreateNew prefix |> ignore

                for step in steps.Tail do
                    let before = DatabaseMigrations.inspect path
                    prefix <- prefix @ [ step.Script ]

                    let mode =
                        match step.Delivery with
                        | AutomaticSchema -> AutomaticUpgrade(before, 256L * 1024L * 1024L)
                        | Manual -> UpgradeExisting
                        | Baseline -> reject ()

                    DatabaseMigrations.run path mode prefix |> ignore

                let actual = DatabaseMigrations.inspect path
                let identifiers = identities steps

                { Protocol = 1
                  CatalogueSha256 = catalogueHash identifiers
                  BaselineSchemaSha256 = baseline
                  SchemaSha256 = actual.SchemaSha256
                  Steps = identifiers }
            finally
                directory.Delete(true)
        with
        | :? MigrationRejected -> reraise ()
        | _ -> reject ()
