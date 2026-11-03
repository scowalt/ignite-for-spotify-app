namespace Ignite.Infrastructure.Data

open System
open System.Data
open System.Globalization
open System.Collections.Generic
open System.IO
open System.Security.Cryptography
open System.Text
open System.Text.RegularExpressions
open System.Text.Json
open DbUp
open DbUp.Engine
open DbUp.Engine.Transactions
open DbUp.Sqlite
open Microsoft.Data.Sqlite

type MigrationScript = { Id: string; Sql: string }

type MigrationEntry =
    { Id: string
      Sha256: string
      AppliedAt: DateTimeOffset }

type MigrationMode =
    | CreateNew
    | UpgradeExisting
    | AdoptLegacy of expectedSchemaSha256: string

type MigrationReport =
    { Applied: string list
      History: MigrationEntry list }

type MigrationInspection =
    { SchemaSha256: string
      History: MigrationEntry list option }

type MigrationRejected(code: string) =
    inherit InvalidOperationException(code)

module private MigrationStorage =
    let validatePath (path: string) =
        if
            not (Path.IsPathFullyQualified(path))
            || not (isNull (FileInfo(path).LinkTarget))
            || Directory.Exists(path)
        then
            raise (MigrationRejected("migration_path_invalid"))

    let hash (content: string) =
        content
        |> UTF8Encoding(false, true).GetBytes
        |> SHA256.HashData
        |> Convert.ToHexStringLower

    let validateCatalogue (scripts: MigrationScript list) =
        if List.isEmpty scripts || scripts.Length > 4096 then
            raise (MigrationRejected("invalid_migration_catalogue"))

        for script in scripts do
            if
                not (Regex.IsMatch(script.Id, "\\A[0-9]{4}_[a-z0-9_]+\\.sql\\z"))
                || script.Id.StartsWith("0000_")
                || script.Id.Length > 128
            then
                raise (MigrationRejected("invalid_migration_catalogue"))

            if
                String.IsNullOrWhiteSpace(script.Sql)
                || script.Sql.StartsWith("\uFEFF", StringComparison.Ordinal)
                || script.Sql.Contains('\r')
                || script.Sql.Contains('\u0000')
                || UTF8Encoding(false, true).GetByteCount(script.Sql) > 1024 * 1024
            then
                raise (MigrationRejected("invalid_migration_encoding"))

        if
            scripts
            |> List.pairwise
            |> List.exists (fun (left, right) ->
                StringComparer.Ordinal.Compare(left.Id.Substring(0, 4), right.Id.Substring(0, 4))
                >= 0)
        then
            raise (MigrationRejected("invalid_migration_catalogue"))

    let validateHistory (scripts: MigrationScript list) (history: MigrationEntry list) =
        if history.Length > scripts.Length then
            raise (MigrationRejected("migration_history_mismatch"))

        for entry, script in List.zip history (List.take history.Length scripts) do
            if entry.Id <> script.Id || entry.Sha256 <> hash script.Sql then
                raise (MigrationRejected("migration_history_mismatch"))

    let command (transaction: SqliteTransaction) () =
        let command = (transaction.Connection |> nonNull).CreateCommand()
        command.Transaction <- transaction
        command.CommandTimeout <- 1
        command :> IDbCommand

    let hasJournal (factory: unit -> IDbCommand) =
        use command = factory ()

        command.CommandText <-
            "SELECT count(*) FROM sqlite_schema WHERE type = 'table' AND name = '__ignite_migrations'"

        Convert.ToInt32(command.ExecuteScalar()) = 1

    let schemaHash (factory: unit -> IDbCommand) =
        use command = factory ()

        command.CommandText <-
            "SELECT type, name, tbl_name, coalesce(sql, '') FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*' AND name <> '__ignite_migrations' ORDER BY type, name"

        use reader = command.ExecuteReader()
        let rows = ResizeArray<string array>()

        while reader.Read() do
            if rows.Count >= 4096 then
                raise (MigrationRejected("schema_inventory_too_large"))

            rows.Add(Array.init 4 reader.GetString)

        let encoded = JsonSerializer.Serialize(rows)

        if encoded.Length > 2 * 1024 * 1024 then
            raise (MigrationRejected("schema_inventory_too_large"))

        hash encoded

    let journalSql =
        "CREATE TABLE __ignite_migrations (position INTEGER NOT NULL UNIQUE CHECK(position > 0), id TEXT NOT NULL PRIMARY KEY, sha256 TEXT NOT NULL CHECK(length(sha256) = 64), applied_at TEXT NOT NULL)"

    let createJournal (factory: unit -> IDbCommand) =
        if not (hasJournal factory) then
            use command = factory ()
            command.CommandText <- journalSql
            command.ExecuteNonQuery() |> ignore

    let history (factory: unit -> IDbCommand) =
        use command = factory ()
        command.CommandText <- "SELECT sql FROM sqlite_schema WHERE name = '__ignite_migrations' AND type = 'table'"

        if command.ExecuteScalar() <> box journalSql then
            raise (MigrationRejected("migration_journal_invalid"))

        command.CommandText <-
            "SELECT count(*) FROM sqlite_schema WHERE tbl_name = '__ignite_migrations' AND type <> 'table' AND sql IS NOT NULL"

        if Convert.ToInt32(command.ExecuteScalar()) <> 0 then
            raise (MigrationRejected("migration_journal_invalid"))

        command.CommandText <- "SELECT id, sha256, applied_at, position FROM __ignite_migrations ORDER BY position"
        use reader = command.ExecuteReader()
        let entries = ResizeArray<MigrationEntry>()

        while reader.Read() do
            if entries.Count >= 4096 || reader.GetInt64(3) <> int64 (entries.Count + 1) then
                raise (MigrationRejected("migration_journal_invalid"))

            let stamp =
                DateTimeOffset.ParseExact(reader.GetString(2), "O", CultureInfo.InvariantCulture)

            if stamp.Offset <> TimeSpan.Zero || stamp > DateTimeOffset.UtcNow.AddSeconds(30) then
                raise (MigrationRejected("migration_journal_invalid"))

            let identifier, checksum = reader.GetString(0), reader.GetString(1)

            if
                identifier.Length > 128
                || not (Regex.IsMatch(identifier, "\\A[0-9]{4}_[a-z0-9_]+\\.sql\\z"))
                || not (Regex.IsMatch(checksum, "\\A[a-f0-9]{64}\\z"))
            then
                raise (MigrationRejected("migration_journal_invalid"))

            entries.Add(
                { Id = identifier
                  Sha256 = checksum
                  AppliedAt = stamp }
            )

        List.ofSeq entries

    let store (factory: unit -> IDbCommand) (clock: TimeProvider) (script: SqlScript) =
        use command = factory ()

        command.CommandText <-
            "INSERT INTO __ignite_migrations(position, id, sha256, applied_at) SELECT count(*) + 1, @id, @sha256, @applied FROM __ignite_migrations"

        for name, value in
            [ "@id", script.Name
              "@sha256", hash script.Contents
              "@applied", clock.GetUtcNow().ToString("O", CultureInfo.InvariantCulture) ] do
            let parameter = command.CreateParameter()
            parameter.ParameterName <- name
            parameter.Value <- value
            command.Parameters.Add(parameter) |> ignore

        command.ExecuteNonQuery() |> ignore

    type ConnectionManager(transaction: SqliteTransaction) =
        let factory = Func<IDbCommand>(command transaction)

        interface IConnectionManager with
            member _.OperationStarting(_, _) =
                { new IDisposable with
                    member _.Dispose() = () }

            member _.ExecuteCommandsWithManagedConnection(action: Action<Func<IDbCommand>>) = action.Invoke(factory)
            member _.ExecuteCommandsWithManagedConnection(action: Func<Func<IDbCommand>, 'T>) = action.Invoke(factory)
            member _.SplitScriptIntoCommands(content) = [ content ]

            member _.TryConnect(_, error) =
                error <- ""
                true

            member _.TransactionMode
                with get () = TransactionMode.NoTransaction
                and set value =
                    if value <> TransactionMode.NoTransaction then
                        raise (MigrationRejected("transaction_ownership_changed"))

            member _.IsScriptOutputLogged
                with get () = false
                and set value =
                    if value then
                        raise (MigrationRejected("migration_output_forbidden"))

            member _.ExecutionTimeoutSeconds
                with get () = Nullable(1)
                and set _ = ()

    type Journal(transaction: SqliteTransaction, clock: TimeProvider) =
        interface IJournal with
            member _.GetExecutedScripts() =
                history (command transaction) |> List.map _.Id |> List.toArray

            member _.EnsureTableExistsAndIsLatestVersion(_) = ()
            member _.StoreExecutedScript(script, factory) = store factory.Invoke clock script

    type LiteralExecutor(configuration: DbUp.Builder.UpgradeConfiguration, schemaOnly: bool) =
        inherit
            SqliteScriptExecutor(
                Func<IConnectionManager>(fun () -> configuration.ConnectionManager),
                (fun () -> configuration.Log),
                null,
                (fun () -> false),
                Seq.empty,
                (fun () -> configuration.Journal)
            )

        let internalTables =
            HashSet<string>([ "sqlite_master"; "sqlite_schema"; "sqlite_sequence" ], StringComparer.OrdinalIgnoreCase)

        override _.PreprocessScriptContents(script, _) = script.Contents

        override _.ExecuteNonQuery(command) =
            let connection = (command.Connection |> nonNull) :?> SqliteConnection
            let handle = connection.Handle |> nonNull

            let authorizer =
                SQLitePCL.strdelegate_authorizer (fun _ action first second _ _ ->
                    if action = SQLitePCL.raw.SQLITE_CREATE_VTABLE && second = "fts5" then
                        for suffix in [ "_data"; "_idx"; "_docsize"; "_config" ] do
                            internalTables.Add(first + suffix) |> ignore

                    let dataMutation =
                        List.contains
                            action
                            [ SQLitePCL.raw.SQLITE_INSERT
                              SQLitePCL.raw.SQLITE_UPDATE
                              SQLitePCL.raw.SQLITE_DELETE ]

                    let reserved (value: string | null) =
                        match value with
                        | null -> false
                        | value -> value.StartsWith("__ignite_", StringComparison.OrdinalIgnoreCase)

                    if
                        List.contains
                            action
                            [ SQLitePCL.raw.SQLITE_TRANSACTION
                              SQLitePCL.raw.SQLITE_SAVEPOINT
                              SQLitePCL.raw.SQLITE_ATTACH
                              SQLitePCL.raw.SQLITE_DETACH
                              SQLitePCL.raw.SQLITE_PRAGMA ]
                        || ((reserved first || reserved second) && action <> SQLitePCL.raw.SQLITE_READ)
                        || (schemaOnly && dataMutation && not (internalTables.Contains(first)))
                    then
                        SQLitePCL.raw.SQLITE_DENY
                    else
                        SQLitePCL.raw.SQLITE_OK)

            if
                SQLitePCL.raw.sqlite3_set_authorizer (handle, authorizer, null)
                <> SQLitePCL.raw.SQLITE_OK
            then
                raise (MigrationRejected("migration_authorizer_unavailable"))

            try
                command.ExecuteNonQuery() |> ignore
            finally
                SQLitePCL.raw.sqlite3_set_authorizer (
                    handle,
                    Unchecked.defaultof<SQLitePCL.strdelegate_authorizer>,
                    null
                )
                |> ignore

    let upgrade transaction (scripts: MigrationScript list) schemaOnly clock onUncommitted =
        let engine =
            DeployChanges.To
                .SqliteDatabase("")
                .WithScripts(scripts |> List.map (fun script -> SqlScript(script.Id, script.Sql)))
                .WithVariablesDisabled()
                .LogToNowhere()

        engine.Configure(fun configuration ->
            configuration.ConnectionManager <- ConnectionManager(transaction)
            configuration.Journal <- Journal(transaction, clock)
            configuration.ScriptExecutor <- LiteralExecutor(configuration, schemaOnly))

        let upgrader = engine.Build()
        upgrader.ScriptExecuted.Add(fun event -> onUncommitted ((event :?> ScriptExecutedEventArgs).Script.Name))
        let result = upgrader.PerformUpgrade()

        if not result.Successful then
            raise (MigrationRejected("migration_batch_failed"))

        result.Scripts |> Seq.map _.Name |> Seq.toList

    let baselineHash baseline =
        use connection =
            new SqliteConnection("Data Source=:memory:;Pooling=False;Foreign Keys=True")

        connection.Open()
        use transaction = connection.BeginTransaction(deferred = false)
        createJournal (command transaction)
        upgrade transaction [ baseline ] true TimeProvider.System ignore |> ignore
        schemaHash (command transaction)

[<RequireQualifiedAccess>]
module DatabaseMigrations =
    let inspect (path: string) : MigrationInspection =
        try
            MigrationStorage.validatePath path

            let builder =
                SqliteConnectionStringBuilder(
                    DataSource = path,
                    Mode = SqliteOpenMode.ReadOnly,
                    Pooling = false,
                    DefaultTimeout = 1
                )

            use connection = new SqliteConnection(builder.ConnectionString)
            connection.Open()
            use transaction = connection.BeginTransaction(deferred = true)
            let factory = MigrationStorage.command transaction

            { SchemaSha256 = MigrationStorage.schemaHash factory
              History =
                if MigrationStorage.hasJournal factory then
                    let entries = MigrationStorage.history factory

                    if entries.IsEmpty then
                        raise (MigrationRejected("migration_journal_invalid"))

                    Some entries
                else
                    None }
        with
        | :? MigrationRejected -> reraise ()
        | _ -> raise (MigrationRejected("migration_inspection_failed"))

    let runObserved
        (path: string)
        (mode: MigrationMode)
        (scripts: MigrationScript list)
        (clock: TimeProvider)
        (onUncommitted: string -> unit)
        : MigrationReport =
        try
            MigrationStorage.validateCatalogue scripts
            MigrationStorage.validatePath path

            match mode with
            | CreateNew ->
                use file =
                    new FileStream(path, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None)

                ()
            | UpgradeExisting -> ()
            | AdoptLegacy expected ->
                if
                    scripts.Length <> 1
                    || scripts.Head.Id <> "0001_initial.sql"
                    || not (Regex.IsMatch(expected, "\\A[a-f0-9]{64}\\z"))
                then
                    raise (MigrationRejected("invalid_legacy_adoption"))

            let builder =
                SqliteConnectionStringBuilder(
                    DataSource = path,
                    Mode = SqliteOpenMode.ReadWrite,
                    Pooling = false,
                    DefaultTimeout = 1,
                    ForeignKeys = Nullable(true)
                )

            use connection = new SqliteConnection(builder.ConnectionString)
            connection.Open()
            use transaction = connection.BeginTransaction(deferred = false)
            let factory = MigrationStorage.command transaction
            let journalExists = MigrationStorage.hasJournal factory

            match mode with
            | UpgradeExisting when not journalExists -> raise (MigrationRejected("explicit_legacy_adoption_required"))
            | AdoptLegacy expected ->
                if
                    journalExists
                    || MigrationStorage.schemaHash factory <> expected
                    || MigrationStorage.baselineHash scripts.Head <> expected
                then
                    raise (MigrationRejected("legacy_schema_mismatch"))
            | _ -> ()

            MigrationStorage.createJournal factory

            match mode with
            | AdoptLegacy _ -> MigrationStorage.store factory clock (SqlScript(scripts.Head.Id, scripts.Head.Sql))
            | _ -> ()

            let previous = MigrationStorage.history factory

            if mode = UpgradeExisting && previous.IsEmpty then
                raise (MigrationRejected("migration_journal_invalid"))

            MigrationStorage.validateHistory scripts previous
            let applied = MigrationStorage.upgrade transaction scripts false clock onUncommitted
            let history = MigrationStorage.history factory
            MigrationStorage.validateHistory scripts history
            transaction.Commit()
            { Applied = applied; History = history }
        with
        | :? MigrationRejected -> reraise ()
        | _ -> raise (MigrationRejected("migration_operation_failed"))

    let run path mode scripts =
        runObserved path mode scripts TimeProvider.System ignore
