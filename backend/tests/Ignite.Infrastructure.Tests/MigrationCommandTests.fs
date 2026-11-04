module Ignite.Infrastructure.Tests.MigrationCommandTests

open System
open System.Diagnostics
open System.IO
open System.Text
open System.Globalization
open System.Threading
open System.Reflection
open System.Text.Json
open Microsoft.Data.Sqlite
open Ignite.Infrastructure.Data
open Ignite.Migrations
open Xunit

let private execute assembly arguments input =
    let start =
        ProcessStartInfo(
            "dotnet",
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false
        )

    for argument in
        [ "exec"
          "--runtimeconfig"
          Path.Combine(AppContext.BaseDirectory, "Ignite.Infrastructure.Tests.runtimeconfig.json")
          "--depsfile"
          Path.Combine(AppContext.BaseDirectory, "Ignite.Infrastructure.Tests.deps.json")
          assembly ]
        @ arguments do
        start.ArgumentList.Add(argument)

    use child = Process.Start(start) |> nonNull
    let stdout = child.StandardOutput.ReadToEndAsync()
    let stderr = child.StandardError.ReadToEndAsync()

    try
        child.StandardInput.Write(input: string)
        child.StandardInput.Close()
        Assert.True(child.WaitForExit(15000), "The migration command must finish within its fixture deadline.")
        child.ExitCode, stdout.GetAwaiter().GetResult(), stderr.GetAwaiter().GetResult()
    finally
        if not child.HasExited then
            child.Kill(entireProcessTree = true)
            child.WaitForExit()

let private command arguments input =
    execute typeof<AssemblyMarker>.Assembly.Location arguments input

let fixturePlan () : MigrationCatalogue.Step list =
    [ { Script = ApplicationMigrations.catalogue().Head
        Delivery = MigrationCatalogue.Baseline }
      { Script =
          { Id = "0002_fixture.sql"
            Sql = "ALTER TABLE user_sessions ADD COLUMN note TEXT;\n" }
        Delivery = MigrationCatalogue.AutomaticSchema } ]

let fixtureManualPlan () =
    fixturePlan ()
    |> List.mapi (fun index step ->
        if index = 0 then
            step
        else
            { step with
                Delivery = MigrationCatalogue.Manual })

let private fixture arguments input =
    execute (Assembly.GetExecutingAssembly().Location) ("migration-cli-fixture" :: arguments) input

let private applyRequest path (descriptor: MigrationCatalogue.Descriptor) (before: MigrationInspection) =
    let entries =
        before.History.Value
        |> List.map (fun entry ->
            {| id = entry.Id
               sha256 = entry.Sha256
               applied_at = entry.AppliedAt.ToString("O", CultureInfo.InvariantCulture) |})

    JsonSerializer.Serialize(
        {| database_path = path
           catalogue_sha256 = descriptor.CatalogueSha256
           schema_sha256 = descriptor.SchemaSha256
           maximum_database_bytes = 1024L * 1024L
           before =
            {| schema = 1
               schema_sha256 = before.SchemaSha256
               history = entries |} |}
    )

[<Fact>]
let ``a verified command applies only its embedded migration plan and refuses stale retries`` () =
    let directory = Directory.CreateTempSubdirectory("ignite-migration-cli-")

    try
        let plan = fixturePlan ()
        let descriptor = MigrationCatalogue.build plan
        let manifest = Path.Combine(directory.FullName, "migration-catalogue.json")
        File.WriteAllBytes(manifest, MigrationCatalogue.encode descriptor)
        let path = Path.Combine(directory.FullName, "application.db")
        DatabaseMigrations.run path CreateNew [ plan.Head.Script ] |> ignore
        let before = DatabaseMigrations.inspect path
        let request = applyRequest path descriptor before
        let code, output, errors = fixture [ "apply"; manifest ] request
        Assert.Equal(0, code)
        Assert.Equal("", errors)
        use result = JsonDocument.Parse(output)
        Assert.Equal("migrated", result.RootElement.GetProperty("outcome").GetString())
        DatabaseMigrations.requireReady path (plan |> List.map _.Script) descriptor.SchemaSha256
        let committed = DatabaseMigrations.inspect path
        let staleCode, _, _ = fixture [ "apply"; manifest ] request
        Assert.Equal(1, staleCode)
        Assert.Equal(committed, DatabaseMigrations.inspect path)
    finally
        directory.Delete(true)

[<Fact>]
let ``pending manual migrations are refused even if their SQL is structurally safe`` () =
    let directory = Directory.CreateTempSubdirectory("ignite-migration-cli-")

    try
        let plan = fixtureManualPlan ()
        let descriptor = MigrationCatalogue.build plan
        let manifest = Path.Combine(directory.FullName, "migration-catalogue.json")
        File.WriteAllBytes(manifest, MigrationCatalogue.encode descriptor)
        let path = Path.Combine(directory.FullName, "application.db")
        DatabaseMigrations.run path CreateNew [ plan.Head.Script ] |> ignore
        let before = DatabaseMigrations.inspect path

        let code, output, _ =
            execute
                (Assembly.GetExecutingAssembly().Location)
                [ "migration-cli-manual-fixture"; "apply"; manifest ]
                (applyRequest path descriptor before)

        Assert.Equal(1, code)
        Assert.Contains("manual_migration_required", output)
        Assert.Equal(before, DatabaseMigrations.inspect path)
    finally
        directory.Delete(true)

[<Fact>]
let ``baseline adoption requires exact image metadata and does not rewrite existing records`` () =
    let directory = Directory.CreateTempSubdirectory("ignite-migration-cli-")

    try
        let plan = ApplicationMigrations.deliveryPlan ()
        let descriptor = MigrationCatalogue.build plan
        let manifest = Path.Combine(directory.FullName, "migration-catalogue.json")
        File.WriteAllBytes(manifest, MigrationCatalogue.encode descriptor)
        let path = Path.Combine(directory.FullName, "application.db")
        use connection = new SqliteConnection($"Data Source={path};Pooling=False")
        connection.Open()
        use setup = connection.CreateCommand()
        setup.CommandText <- plan.Head.Script.Sql
        setup.ExecuteNonQuery() |> ignore

        setup.CommandText <-
            "INSERT INTO user_sessions(id, spotify_refresh_token, created_at, updated_at) VALUES ('fixture', 'not-public-fixture-value', '2026-01-01', '2026-01-01')"

        setup.ExecuteNonQuery() |> ignore
        connection.Close()

        let _, beforeJson, _ =
            command [ "inspect" ] (JsonSerializer.Serialize({| database_path = path |}))

        use before = JsonDocument.Parse(beforeJson)

        let request =
            JsonSerializer.Serialize(
                {| database_path = path
                   catalogue_sha256 = descriptor.CatalogueSha256
                   schema_sha256 = descriptor.SchemaSha256
                   before = before.RootElement |}
            )

        let code, output, errors = command [ "adopt"; manifest ] request
        Assert.Equal(0, code)
        Assert.Equal("", errors)
        Assert.DoesNotContain("not-public-fixture-value", output)
        DatabaseMigrations.requireReady path (plan |> List.map _.Script) descriptor.SchemaSha256
        connection.Open()
        setup.CommandText <- "SELECT spotify_refresh_token FROM user_sessions WHERE id = 'fixture'"
        Assert.Equal("not-public-fixture-value", setup.ExecuteScalar() :?> string)
        connection.Close()
        let repeated, _, _ = command [ "adopt"; manifest ] request
        Assert.Equal(1, repeated)
    finally
        directory.Delete(true)

[<Fact>]
let ``explicit settlement recovers an interrupted SQLite transaction without running pending migrations`` () =
    let directory = Directory.CreateTempSubdirectory("ignite-migration-cli-")

    try
        let path = Path.Combine(directory.FullName, "application.db")
        let baseline = DatabaseMigrationTests.interruptionCatalogueWithSpill().Head
        DatabaseMigrations.run path CreateNew [ baseline ] |> ignore
        let before = DatabaseMigrations.inspect path
        let ready = Path.Combine(directory.FullName, "ready")

        let start =
            ProcessStartInfo(
                "dotnet",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false
            )

        for argument in
            [ Assembly.GetExecutingAssembly().Location
              "hold-large-migration"
              path
              ready ] do
            start.ArgumentList.Add(argument)

        use child = Process.Start(start) |> nonNull

        try
            let deadline = DateTime.UtcNow.AddSeconds(15)

            while not (File.Exists(ready)) && not child.HasExited && DateTime.UtcNow < deadline do
                Thread.Sleep(10)

            Assert.True(File.Exists(ready))
        finally
            if not child.HasExited then
                child.Kill(entireProcessTree = true)

            Assert.True(child.WaitForExit(10000))

        let request = JsonSerializer.Serialize({| database_path = path |})
        let readOnlyCode, _, _ = command [ "inspect" ] request
        Assert.Equal(1, readOnlyCode)
        let stoppedCode, _, _ = command [ "inspect-stopped" ] request
        Assert.Equal(1, stoppedCode)
        let code, output, errors = command [ "settle" ] request
        Assert.Equal(0, code)
        Assert.Equal("", errors)
        Assert.Contains("settled", output)
        Assert.Equal(before, DatabaseMigrations.inspect path)
        DatabaseMigrations.requireReady path [ baseline ] before.SchemaSha256
    finally
        directory.Delete(true)

[<Fact>]
let ``even a no-op apply requires a valid explicit database budget`` () =
    let directory = Directory.CreateTempSubdirectory("ignite-migration-cli-")

    try
        let plan = ApplicationMigrations.deliveryPlan ()
        let descriptor = MigrationCatalogue.build plan
        let manifest = Path.Combine(directory.FullName, "migration-catalogue.json")
        File.WriteAllBytes(manifest, MigrationCatalogue.encode descriptor)
        let path = Path.Combine(directory.FullName, "application.db")
        DatabaseMigrations.run path CreateNew (plan |> List.map _.Script) |> ignore
        let before = DatabaseMigrations.inspect path

        let invalid =
            (applyRequest path descriptor before)
                .Replace("\"maximum_database_bytes\":1048576", "\"maximum_database_bytes\":true")

        let code, _, _ = command [ "apply"; manifest ] invalid
        Assert.Equal(1, code)
        Assert.Equal(before, DatabaseMigrations.inspect path)
    finally
        directory.Delete(true)

[<Fact>]
let ``the command builds source-bound metadata without starting the application`` () =
    let code, output, errors = command [ "build-manifest" ] ""
    Assert.Equal(0, code)
    Assert.Equal("", errors)

    let descriptor =
        MigrationCatalogue.decode (ApplicationMigrations.deliveryPlan ()) (Encoding.UTF8.GetBytes(output))

    Assert.Equal("0001_initial.sql", Assert.Single(descriptor.Steps).Id)

[<Fact>]
let ``describe reads validated image metadata without accessing a database`` () =
    let directory = Directory.CreateTempSubdirectory("ignite-migration-cli-")

    try
        let manifest = Path.Combine(directory.FullName, "migration-catalogue.json")
        let plan = ApplicationMigrations.deliveryPlan ()
        let descriptor = MigrationCatalogue.build plan
        File.WriteAllBytes(manifest, MigrationCatalogue.encode descriptor)
        let code, output, errors = command [ "describe"; manifest ] ""
        Assert.Equal(0, code)
        Assert.Equal("", errors)
        Assert.Equal(descriptor, MigrationCatalogue.decode plan (Encoding.UTF8.GetBytes(output)))
        Assert.Single(Directory.GetFiles(directory.FullName)) |> ignore
    finally
        directory.Delete(true)

[<Fact>]
let ``inspect emits only schema and history metadata and never creates a missing database`` () =
    let directory = Directory.CreateTempSubdirectory("ignite-migration-cli-")

    try
        let path = Path.Combine(directory.FullName, "application.db")
        let request = System.Text.Json.JsonSerializer.Serialize({| database_path = path |})
        let missingCode, missingOutput, _ = command [ "inspect" ] request
        Assert.Equal(1, missingCode)
        Assert.DoesNotContain(path, missingOutput)
        Assert.False(File.Exists(path))
        let stoppedCode, _, _ = command [ "inspect-stopped" ] request
        Assert.Equal(1, stoppedCode)
        Assert.False(File.Exists(path))
        let catalogue = ApplicationMigrations.catalogue ()
        DatabaseMigrations.run path CreateNew catalogue |> ignore
        let code, output, errors = command [ "inspect" ] request
        Assert.Equal(0, code)
        Assert.Equal("", errors)
        use result = System.Text.Json.JsonDocument.Parse(output)

        Assert.Equal(
            (DatabaseMigrations.inspect path).SchemaSha256,
            result.RootElement.GetProperty("schema_sha256").GetString()
        )

        Assert.Equal(1, result.RootElement.GetProperty("history").GetArrayLength())
        Assert.DoesNotContain("CREATE TABLE", output)
        Assert.DoesNotContain(path, output)
    finally
        directory.Delete(true)
