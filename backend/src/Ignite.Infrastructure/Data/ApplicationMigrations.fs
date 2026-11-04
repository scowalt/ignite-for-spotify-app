namespace Ignite.Infrastructure.Data

open System
open System.IO
open System.Text

[<RequireQualifiedAccess>]
module ApplicationMigrations =
    let catalogue () : MigrationScript list =
        let assembly = typeof<MigrationScript>.Assembly
        let prefix = "Ignite.Migrations."

        let names =
            assembly.GetManifestResourceNames()
            |> Array.filter (fun name -> name.StartsWith(prefix, StringComparison.Ordinal))
            |> Array.sortWith (fun left right -> StringComparer.Ordinal.Compare(left, right))

        if names.Length > 4096 then
            raise (MigrationRejected("migration_catalogue_too_large"))

        let mutable total = 0L

        names
        |> Array.map (fun name ->
            use stream = assembly.GetManifestResourceStream(name) |> nonNull

            total <- total + stream.Length

            if stream.Length > 1024L * 1024L || total > 16L * 1024L * 1024L then
                raise (MigrationRejected("migration_resource_too_large"))

            use content = new MemoryStream()
            stream.CopyTo(content)

            { Id = name.Substring(prefix.Length)
              Sql = UTF8Encoding(false, true).GetString(content.ToArray()) })
        |> Array.toList

    let deliveryPlan () =
        use stream =
            typeof<MigrationScript>.Assembly.GetManifestResourceStream("Ignite.MigrationDelivery.json")
            |> nonNull

        if stream.Length > 1024L * 1024L then
            raise (MigrationRejected("migration_resource_too_large"))

        use content = new MemoryStream()
        stream.CopyTo(content)
        MigrationCatalogue.plan (catalogue ()) (content.ToArray())
