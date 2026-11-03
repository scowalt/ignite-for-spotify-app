module Ignite.Infrastructure.Tests.LegacySchema

open System.IO
open System.Reflection
open Microsoft.Data.Sqlite

let private execute resource path =
    use source =
        Assembly.GetExecutingAssembly().GetManifestResourceStream(resource) |> nonNull

    use text = new StreamReader(source)
    use connection = new SqliteConnection($"Data Source={path};Pooling=False")
    connection.Open()
    use command = connection.CreateCommand()
    command.CommandText <- text.ReadToEnd()
    command.ExecuteNonQuery() |> ignore

let seed path =
    execute "Ignite.Tests.LegacyRows.sql" path

let create path =
    execute "Ignite.Tests.LegacySchema.sql" path
    use connection = new SqliteConnection($"Data Source={path};Pooling=False")
    connection.Open()
    use command = connection.CreateCommand()
    command.CommandText <- "PRAGMA journal_mode=WAL;"
    command.ExecuteScalar() |> ignore
