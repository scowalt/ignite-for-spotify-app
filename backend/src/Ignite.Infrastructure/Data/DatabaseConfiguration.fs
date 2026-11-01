namespace Ignite.Infrastructure.Data

open System
open System.IO
open Microsoft.Data.Sqlite

type DatabaseStartupOptions(requireExisting: bool) =
    member _.RequireExisting = requireExisting

[<RequireQualifiedAccess>]
module DatabaseConfiguration =
    let private isRemoteConnectionString (connectionString: string) =
        connectionString.StartsWith("libsql://", StringComparison.OrdinalIgnoreCase)
        || connectionString.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
        || connectionString.StartsWith("https://", StringComparison.OrdinalIgnoreCase)

    let validateConnectionString (requireExisting: bool) (connectionString: string) =
        if String.IsNullOrWhiteSpace(connectionString) then
            invalidArg (nameof connectionString) "The application database connection string is required."

        if isRemoteConnectionString connectionString then
            invalidArg
                (nameof connectionString)
                "Remote and libSQL database URLs are not supported. Configure a local SQLite file."

        let builder =
            try
                SqliteConnectionStringBuilder(connectionString)
            with :? ArgumentException as ex ->
                raise (ArgumentException("The application database connection string is invalid.", nameof connectionString, ex))

        if String.IsNullOrWhiteSpace(builder.DataSource) then
            invalidArg (nameof connectionString) "The application database connection string must specify Data Source."

        if requireExisting then
            if builder.DataSource.Equals(":memory:", StringComparison.OrdinalIgnoreCase) then
                invalidArg (nameof connectionString) "Production requires a persistent SQLite database file."

            if not (Path.IsPathRooted(builder.DataSource)) then
                invalidArg (nameof connectionString) "Production requires an absolute SQLite database path."

            if not (File.Exists(builder.DataSource)) then
                raise (FileNotFoundException("The production SQLite database file does not exist.", builder.DataSource))

            try
                use stream =
                    new FileStream(
                        builder.DataSource,
                        FileMode.Open,
                        FileAccess.ReadWrite,
                        FileShare.ReadWrite ||| FileShare.Delete
                    )

                if not stream.CanWrite then
                    raise (UnauthorizedAccessException("The production SQLite database file is not writable."))
            with
            | :? UnauthorizedAccessException ->
                raise (UnauthorizedAccessException("The production SQLite database file is not writable."))
            | :? IOException as ex ->
                raise (IOException("The production SQLite database file could not be opened for writing.", ex))

            builder.Mode <- SqliteOpenMode.ReadWrite

        builder.ConnectionString
