namespace Ignite.Infrastructure.Data

open System

type MigrationScript = { Id: string; Sql: string }

type MigrationEntry =
    { Id: string
      Sha256: string
      AppliedAt: DateTimeOffset }

type MigrationInspection =
    { SchemaSha256: string
      History: MigrationEntry list option }

type MigrationMode =
    | CreateNew
    | UpgradeExisting
    | AdoptLegacy of expectedSchemaSha256: string
    | AutomaticUpgrade of expectedBefore: MigrationInspection * maximumDatabaseBytes: int64
    | VerifiedUpgrade of
        expectedBefore: MigrationInspection *
        expectedSchemaSha256: string *
        maximumDatabaseBytes: int64

type MigrationReport =
    { Applied: string list
      History: MigrationEntry list }

type MigrationRejected(code: string) =
    inherit InvalidOperationException(code)
