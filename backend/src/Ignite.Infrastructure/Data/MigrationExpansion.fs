namespace Ignite.Infrastructure.Data

open System
open System.Data
open System.Security.Cryptography
open System.Text
open System.Text.RegularExpressions
open Microsoft.Data.Sqlite

module internal MigrationExpansion =
    type SchemaObject =
        { Kind: string
          Name: string
          Table: string
          Sql: string
          RootPage: int64 }

    type Column =
        { Name: string
          DeclaredType: string
          Required: int64
          Default: string option
          PrimaryKey: int64
          Hidden: int64 }

    type Table =
        { Name: string
          Columns: Column list
          WithoutRowid: bool
          DataHash: byte array }

    type Snapshot =
        { Objects: Map<string, SchemaObject>
          Tables: Table list
          Key: byte array }

        interface IDisposable with
            member this.Dispose() =
                CryptographicOperations.ZeroMemory(this.Key)

    let private reject () =
        raise (MigrationRejected("automatic_schema_expansion_required"))

    let private quote (name: string) =
        "\"" + name.Replace("\"", "\"\"") + "\""

    let private command (transaction: SqliteTransaction) sql =
        let result = (transaction.Connection |> nonNull).CreateCommand()
        result.Transaction <- transaction
        result.CommandTimeout <- 1
        result.CommandText <- sql
        result

    let private objects transaction =
        use query =
            command
                transaction
                "SELECT type, name, tbl_name, coalesce(sql, ''), rootpage FROM sqlite_schema WHERE (name NOT GLOB 'sqlite_*' OR name = 'sqlite_sequence') AND name <> '__ignite_migrations' ORDER BY name"

        use rows = query.ExecuteReader()
        let result = ResizeArray<string * SchemaObject>()

        while rows.Read() do
            if result.Count >= 4096 then
                reject ()

            let value =
                { Kind = rows.GetString(0)
                  Name = rows.GetString(1)
                  Table = rows.GetString(2)
                  Sql = rows.GetString(3)
                  RootPage = rows.GetInt64(4) }

            result.Add(value.Name, value)

        Map.ofSeq result

    let private columns transaction name =
        use query = command transaction ("PRAGMA table_xinfo(" + quote name + ")")
        use rows = query.ExecuteReader()
        let result = ResizeArray<Column>()

        while rows.Read() do
            if result.Count >= 2048 then
                reject ()

            result.Add(
                { Name = rows.GetString(1)
                  DeclaredType = rows.GetString(2)
                  Required = rows.GetInt64(3)
                  Default = if rows.IsDBNull(4) then None else Some(rows.GetString(4))
                  PrimaryKey = rows.GetInt64(5)
                  Hidden = rows.GetInt64(6) }
            )

        List.ofSeq result

    let private dataHash transaction (key: byte array) name (fields: Column list) withoutRowid =
        let order, identity =
            if withoutRowid then
                let keys =
                    fields
                    |> List.filter (fun field -> field.PrimaryKey > 0L)
                    |> List.sortBy _.PrimaryKey

                if keys.IsEmpty then
                    reject ()

                keys
                |> List.map (fun field -> quote field.Name + " COLLATE BINARY")
                |> String.concat ",",
                ""
            else
                let alias =
                    [ "rowid"; "_rowid_"; "oid" ]
                    |> List.tryFind (fun name ->
                        fields
                        |> List.forall (fun field ->
                            not (String.Equals(field.Name, name, StringComparison.OrdinalIgnoreCase))))

                match alias with
                | None -> reject ()
                | Some name -> quote name, quote name + ","

        let selection =
            fields
            |> List.map (fun field ->
                let name = quote field.Name

                "typeof("
                + name
                + "), CASE WHEN typeof("
                + name
                + ") = 'text' THEN CAST("
                + name
                + " AS BLOB) ELSE "
                + name
                + " END")
            |> String.concat ","

        use query =
            command transaction ("SELECT " + identity + selection + " FROM " + quote name + " ORDER BY " + order)

        use rows = query.ExecuteReader()
        use digest = IncrementalHash.CreateHMAC(HashAlgorithmName.SHA256, key)

        let append (value: byte array) =
            digest.AppendData(BitConverter.GetBytes(value.Length))
            digest.AppendData(value)

        while rows.Read() do
            digest.AppendData([| 255uy |])
            let offset = if withoutRowid then 0 else 1

            if not withoutRowid then
                append (BitConverter.GetBytes(rows.GetInt64(0)))

            for index in 0 .. fields.Length - 1 do
                let position = offset + index * 2
                let kind = rows.GetString(position)
                append (Encoding.ASCII.GetBytes(kind))

                match kind with
                | "null" -> append Array.empty
                | "integer" -> append (BitConverter.GetBytes(rows.GetInt64(position + 1)))
                | "real" -> append (BitConverter.GetBytes(rows.GetDouble(position + 1)))
                | "text"
                | "blob" -> append (rows.GetFieldValue<byte array>(position + 1))
                | _ -> reject ()

        digest.GetHashAndReset()

    let limitDatabase transaction maximumBytes =
        if maximumBytes <= 0L || maximumBytes > 256L * 1024L * 1024L then
            reject ()

        use limit = command transaction "PRAGMA page_size"
        let pageSize = limit.ExecuteScalar() :?> int64
        limit.CommandText <- "PRAGMA page_count"
        let pages = limit.ExecuteScalar() :?> int64
        let maximumPages = maximumBytes / pageSize

        if maximumPages < pages || maximumPages <= 0L then
            reject ()

        limit.CommandText <-
            "PRAGMA max_page_count = "
            + maximumPages.ToString(Globalization.CultureInfo.InvariantCulture)

        if limit.ExecuteScalar() :?> int64 <> maximumPages then
            reject ()

    let capture transaction =
        let key = RandomNumberGenerator.GetBytes(32)

        try
            let schema = objects transaction
            use query = command transaction "PRAGMA table_list"
            let tables = ResizeArray<string * bool>()

            do
                use rows = query.ExecuteReader()

                while rows.Read() do
                    let name = rows.GetString(1)

                    if
                        rows.GetString(0) = "main"
                        && rows.GetString(2) = "table"
                        && schema.ContainsKey(name)
                    then
                        tables.Add(name, rows.GetInt64(4) <> 0L)

            let snapshots =
                [ for name, withoutRowid in tables do
                      let fields = columns transaction name

                      yield
                          { Name = name
                            Columns = fields
                            WithoutRowid = withoutRowid
                            DataHash = dataHash transaction key name fields withoutRowid } ]

            { Objects = schema
              Tables = snapshots
              Key = key }
        with _ ->
            CryptographicOperations.ZeroMemory(key)
            reraise ()

    let private verifyTableDefinition (previous: SchemaObject) (current: SchemaObject) =
        if previous.Sql = current.Sql then
            ()
        else
            let closing = previous.Sql.LastIndexOf(')')
            let newClosing = current.Sql.LastIndexOf(')')

            if closing < 0 || newClosing <= closing then
                reject ()

            let prefix = previous.Sql.Substring(0, closing)

            if
                not (current.Sql.StartsWith(prefix + ",", StringComparison.Ordinal))
                || current.Sql.Substring(newClosing) <> previous.Sql.Substring(closing)
            then
                reject ()

            let additions =
                current.Sql.Substring(closing + 1, newClosing - closing - 1).Split(',')

            let declaration =
                "\\A\\s*(?:[A-Za-z_][A-Za-z0-9_]*|\"[A-Za-z_][A-Za-z0-9_]*\"|\\[[A-Za-z_][A-Za-z0-9_]*\\]|`[A-Za-z_][A-Za-z0-9_]*`)\\s+(?:TEXT|INTEGER|REAL|BLOB|NUMERIC)\\s*(?:NULL\\s*)?(?:DEFAULT\\s+NULL\\s*)?\\z"

            if
                additions
                |> Array.exists (fun value ->
                    not (Regex.IsMatch(value, declaration, RegexOptions.IgnoreCase ||| RegexOptions.CultureInvariant)))
            then
                reject ()

    let private verifyIndex transaction (value: SchemaObject) =
        use query = command transaction ("PRAGMA index_list(" + quote value.Table + ")")
        let mutable found = false

        do
            use rows = query.ExecuteReader()

            while rows.Read() do
                if rows.GetString(1) = value.Name then
                    if rows.GetInt64(2) <> 0L || rows.GetInt64(4) <> 0L then
                        reject ()

                    found <- true

        if not found then
            reject ()

        query.CommandText <- "PRAGMA index_xinfo(" + quote value.Name + ")"
        use fields = query.ExecuteReader()

        while fields.Read() do
            if fields.GetInt64(5) = 1L && fields.GetInt64(1) < 0L then
                reject ()

    let verify transaction (before: Snapshot) =
        let after = objects transaction

        for KeyValue(name, previous) in before.Objects do
            match after.TryFind(name) with
            | None -> reject ()
            | Some current ->
                if
                    current.Kind <> previous.Kind
                    || current.Table <> previous.Table
                    || current.RootPage <> previous.RootPage
                then
                    reject ()

                if current.Kind = "table" then
                    verifyTableDefinition previous current
                elif current.Sql <> previous.Sql then
                    reject ()

        for table in before.Tables do
            let current = columns transaction table.Name

            if
                current.Length < table.Columns.Length
                || List.take table.Columns.Length current <> table.Columns
            then
                reject ()

            for added in List.skip table.Columns.Length current do
                if
                    added.Required <> 0L
                    || added.PrimaryKey <> 0L
                    || added.Hidden <> 0L
                    || (added.Default
                        |> Option.exists (fun value ->
                            not (String.Equals(value, "NULL", StringComparison.OrdinalIgnoreCase))))
                then
                    reject ()

            let actual =
                dataHash transaction before.Key table.Name table.Columns table.WithoutRowid

            if not (CryptographicOperations.FixedTimeEquals(table.DataHash, actual)) then
                reject ()

        for KeyValue(name, value) in after do
            if not (before.Objects.ContainsKey(name)) then
                match value.Kind with
                | "table" ->
                    use query = command transaction "PRAGMA table_list"
                    use tables = query.ExecuteReader()
                    let mutable ordinary = false

                    while tables.Read() do
                        if
                            tables.GetString(0) = "main"
                            && tables.GetString(1) = name
                            && tables.GetString(2) = "table"
                        then
                            ordinary <- true

                    if not ordinary then
                        reject ()
                | "index" -> verifyIndex transaction value
                | _ -> reject ()
