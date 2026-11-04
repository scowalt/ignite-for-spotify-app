namespace Ignite.Infrastructure.Data

open System
open System.IO
open Microsoft.Data.Sqlite

[<RequireQualifiedAccess>]
module DatabaseStartup =
    let initialize
        connectionString
        requireExisting
        (plan: MigrationCatalogue.Step list)
        (descriptor: MigrationCatalogue.Descriptor option)
        =
        try
            let verified =
                if requireExisting then
                    match descriptor with
                    | None -> raise (MigrationRejected("migration_manifest_required"))
                    | Some value -> Some(MigrationCatalogue.decode plan (MigrationCatalogue.encode value))
                else
                    None

            let normalized =
                SqliteConnectionStringBuilder(
                    DatabaseConfiguration.validateConnectionString requireExisting connectionString
                )

            if
                normalized.DataSource = ":memory:"
                || normalized.DataSource.StartsWith("file:", StringComparison.OrdinalIgnoreCase)
            then
                raise (MigrationRejected("migration_path_invalid"))

            let path = Path.GetFullPath(normalized.DataSource)
            normalized.DataSource <- path
            normalized.Mode <- SqliteOpenMode.ReadWrite
            normalized.ForeignKeys <- Nullable(true)
            let scripts = plan |> List.map _.Script

            match verified with
            | Some metadata -> DatabaseMigrations.requireReady path scripts metadata.SchemaSha256
            | None ->
                let mode =
                    if File.Exists(path) then
                        UpgradeExisting
                    else
                        Directory.CreateDirectory(Path.GetDirectoryName(path) |> nonNull) |> ignore
                        CreateNew

                DatabaseMigrations.run path mode scripts |> ignore

            let startup =
                SqliteConnectionStringBuilder(normalized.ConnectionString, Pooling = false)

            use connection = new SqliteConnection(startup.ConnectionString)
            connection.Open()
            use command = connection.CreateCommand()
            command.CommandText <- "PRAGMA journal_mode=WAL;"

            if command.ExecuteScalar() <> box "wal" then
                raise (MigrationRejected("database_wal_required"))

            normalized.ConnectionString
        with
        | :? MigrationRejected -> reraise ()
        | _ -> raise (MigrationRejected("database_startup_failed"))
