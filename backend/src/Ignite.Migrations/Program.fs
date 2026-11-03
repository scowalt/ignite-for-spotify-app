namespace Ignite.Migrations

open System
open System.Globalization
open System.IO
open System.Text.Json
open System.Text.RegularExpressions
open Ignite.Infrastructure.Data

type AssemblyMarker = private AssemblyMarker of unit

module private Wire =
    let reject () =
        raise (MigrationRejected("migration_command_invalid"))

    let keys expected (value: JsonElement) =
        if value.ValueKind <> JsonValueKind.Object then
            reject ()

        if
            (value.EnumerateObject() |> Seq.map _.Name |> Seq.sort |> Seq.toList)
            <> List.sort expected
        then
            reject ()

    let input expected =
        use stdin = Console.OpenStandardInput()
        use content = new MemoryStream()
        let buffer = Array.zeroCreate<byte> 8192
        let mutable count = stdin.Read(buffer, 0, buffer.Length)

        while count > 0 do
            if content.Length + int64 count > 2L * 1024L * 1024L then
                reject ()

            content.Write(buffer, 0, count)
            count <- stdin.Read(buffer, 0, buffer.Length)

        let document =
            JsonDocument.Parse(content.ToArray(), JsonDocumentOptions(MaxDepth = 8))

        try
            keys expected document.RootElement
            document
        with _ ->
            document.Dispose()
            reraise ()

    let json action =
        use output = new MemoryStream()
        use writer = new Utf8JsonWriter(output)
        action writer
        writer.Flush()

        if output.Length > 2L * 1024L * 1024L then
            reject ()

        output.ToArray()

    let writeInspection (writer: Utf8JsonWriter) (inspection: MigrationInspection) =
        writer.WriteStartObject()
        writer.WriteNumber("schema", 1)
        writer.WriteString("schema_sha256", inspection.SchemaSha256)

        match inspection.History with
        | None -> writer.WriteNull("history")
        | Some entries ->
            writer.WriteStartArray("history")

            for entry in entries do
                writer.WriteStartObject()
                writer.WriteString("id", entry.Id)
                writer.WriteString("sha256", entry.Sha256)
                writer.WriteString("applied_at", entry.AppliedAt.ToString("O", CultureInfo.InvariantCulture))
                writer.WriteEndObject()

            writer.WriteEndArray()

        writer.WriteEndObject()

    let inspection (value: JsonElement) : MigrationInspection =
        keys [ "schema"; "schema_sha256"; "history" ] value

        if value.GetProperty("schema").GetInt32() <> 1 then
            reject ()

        let schemaHash = value.GetProperty("schema_sha256").GetString() |> nonNull

        if not (Regex.IsMatch(schemaHash, "\\A[a-f0-9]{64}\\z")) then
            reject ()

        let history = value.GetProperty("history")

        let entries =
            if history.ValueKind = JsonValueKind.Null then
                None
            else
                if history.GetArrayLength() > 4096 || history.GetArrayLength() = 0 then
                    reject ()

                history.EnumerateArray()
                |> Seq.map (fun row ->
                    keys [ "id"; "sha256"; "applied_at" ] row
                    let id = row.GetProperty("id").GetString() |> nonNull
                    let checksum = row.GetProperty("sha256").GetString() |> nonNull

                    if
                        id.Length > 128
                        || not (Regex.IsMatch(id, "\\A[0-9]{4}_[a-z0-9_]+\\.sql\\z"))
                        || not (Regex.IsMatch(checksum, "\\A[a-f0-9]{64}\\z"))
                    then
                        reject ()

                    let applied =
                        DateTimeOffset.ParseExact(
                            row.GetProperty("applied_at").GetString() |> nonNull,
                            "O",
                            CultureInfo.InvariantCulture
                        )

                    if
                        applied.Offset <> TimeSpan.Zero
                        || applied > DateTimeOffset.UtcNow.AddSeconds(30)
                    then
                        reject ()

                    { Id = id
                      Sha256 = checksum
                      AppliedAt = applied })
                |> Seq.toList
                |> Some

        { SchemaSha256 = schemaHash
          History = entries }

    let result (outcome: string) inspection =
        json (fun writer ->
            writer.WriteStartObject()
            writer.WriteNumber("schema", 1)
            writer.WriteString("outcome", outcome)
            writer.WritePropertyName("inspection")
            writeInspection writer inspection
            writer.WriteEndObject())

    let pending (descriptor: MigrationCatalogue.Descriptor) (before: MigrationInspection) =
        match before.History with
        | None -> raise (MigrationRejected("explicit_legacy_adoption_required"))
        | Some history ->
            if history.Length > descriptor.Steps.Length then
                reject ()

            for applied, expected in List.zip history (List.take history.Length descriptor.Steps) do
                if applied.Id <> expected.Id || applied.Sha256 <> expected.Sha256 then
                    reject ()

            List.skip history.Length descriptor.Steps

module Program =
    let run getPlan arguments =
        try
            let plan = getPlan ()

            let output =
                match arguments with
                | [| "build-manifest" |] -> plan |> MigrationCatalogue.build |> MigrationCatalogue.encode
                | [| "describe"; manifest |] ->
                    let descriptor = MigrationCatalogue.readFile plan manifest
                    MigrationCatalogue.encode descriptor
                | [| "inspect" |] ->
                    use request = Wire.input [ "database_path" ]
                    let path = request.RootElement.GetProperty("database_path").GetString() |> nonNull
                    let inspection = DatabaseMigrations.inspect path
                    Wire.json (fun writer -> Wire.writeInspection writer inspection)
                | [| "settle" |] ->
                    use request = Wire.input [ "database_path" ]
                    let path = request.RootElement.GetProperty("database_path").GetString() |> nonNull
                    Wire.result "settled" (DatabaseMigrations.settleAndInspect path)
                | [| "adopt"; manifest |] ->
                    let descriptor = MigrationCatalogue.readFile plan manifest

                    use request =
                        Wire.input [ "database_path"; "catalogue_sha256"; "schema_sha256"; "before" ]

                    let root = request.RootElement

                    if
                        descriptor.Steps.Length <> 1
                        || descriptor.Steps.Head.Delivery <> MigrationCatalogue.Baseline
                        || descriptor.SchemaSha256 <> descriptor.BaselineSchemaSha256
                    then
                        Wire.reject ()

                    if
                        root.GetProperty("catalogue_sha256").GetString() <> descriptor.CatalogueSha256
                        || root.GetProperty("schema_sha256").GetString() <> descriptor.SchemaSha256
                    then
                        Wire.reject ()

                    let before = Wire.inspection (root.GetProperty("before"))

                    if before.History.IsSome || before.SchemaSha256 <> descriptor.BaselineSchemaSha256 then
                        Wire.reject ()

                    let path = root.GetProperty("database_path").GetString() |> nonNull

                    if DatabaseMigrations.inspect path <> before then
                        raise (MigrationRejected("migration_precondition_changed"))

                    DatabaseMigrations.run path (AdoptLegacy before.SchemaSha256) (plan |> List.map _.Script)
                    |> ignore

                    Wire.result "adopted" (DatabaseMigrations.inspect path)
                | [| "apply"; manifest |] ->
                    let descriptor = MigrationCatalogue.readFile plan manifest

                    use request =
                        Wire.input
                            [ "database_path"
                              "catalogue_sha256"
                              "schema_sha256"
                              "before"
                              "maximum_database_bytes" ]

                    let root = request.RootElement

                    if
                        root.GetProperty("catalogue_sha256").GetString() <> descriptor.CatalogueSha256
                        || root.GetProperty("schema_sha256").GetString() <> descriptor.SchemaSha256
                    then
                        Wire.reject ()

                    let before = Wire.inspection (root.GetProperty("before"))
                    let pending = Wire.pending descriptor before

                    if
                        pending
                        |> List.exists (fun step -> step.Delivery <> MigrationCatalogue.AutomaticSchema)
                    then
                        raise (MigrationRejected("manual_migration_required"))

                    let path = root.GetProperty("database_path").GetString() |> nonNull

                    if DatabaseMigrations.inspect path <> before then
                        raise (MigrationRejected("migration_precondition_changed"))

                    let scripts = plan |> List.map _.Script
                    let maximum = root.GetProperty("maximum_database_bytes").GetInt64()

                    if maximum <= 0L || maximum > 256L * 1024L * 1024L then
                        Wire.reject ()

                    if pending.IsEmpty then
                        DatabaseMigrations.requireReady path scripts descriptor.SchemaSha256
                        Wire.result "unchanged" before
                    else
                        DatabaseMigrations.run path (VerifiedUpgrade(before, descriptor.SchemaSha256, maximum)) scripts
                        |> ignore

                        Wire.result "migrated" (DatabaseMigrations.inspect path)
                | _ -> Wire.reject ()

            use stdout = Console.OpenStandardOutput()
            stdout.Write(output)
            0
        with
        | :? MigrationRejected as error ->
            Console.WriteLine(
                JsonSerializer.Serialize(
                    {| outcome = "rejected"
                       reason = error.Message |}
                )
            )

            1
        | _ ->
            Console.WriteLine("{\"outcome\":\"rejected\",\"reason\":\"migration_command_failed\"}")
            1

    [<EntryPoint>]
    let main arguments =
        run ApplicationMigrations.deliveryPlan arguments
