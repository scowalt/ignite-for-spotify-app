namespace Ignite.Api

open System
open Ignite.Infrastructure.Data
open Microsoft.Extensions.Configuration
open Microsoft.Extensions.Hosting

module DatabaseBootstrap =
    let initialize (configuration: IConfiguration) (environment: IHostEnvironment) : string * bool =
        let configuredConnection = configuration.GetConnectionString("Database")

        let connectionString =
            if String.IsNullOrEmpty(configuredConnection) then
                "Data Source=/app/data/ignite.db;Default Timeout=60"
            else
                configuredConnection

        let requireExistingDatabase =
            let configuredValue = configuration.["Database:RequireExisting"]

            if String.IsNullOrEmpty(configuredValue) then
                environment.IsProduction()
            else
                match Boolean.TryParse(configuredValue) with
                | true, value -> value
                | false, _ ->
                    invalidArg
                        "Database:RequireExisting"
                        "Database:RequireExisting must be true or false."

        if environment.IsProduction() && not requireExistingDatabase then
            invalidArg "Database:RequireExisting" "Production cannot initialize a missing database."

        let migrationPlan = ApplicationMigrations.deliveryPlan ()

        let migrationDescriptor =
            if requireExistingDatabase then
                Some(
                    MigrationCatalogue.readFile
                        migrationPlan
                        (IO.Path.Combine(AppContext.BaseDirectory, "migration-catalogue.json"))
                )
            else
                None

        DatabaseStartup.initialize connectionString requireExistingDatabase migrationPlan migrationDescriptor,
        requireExistingDatabase
