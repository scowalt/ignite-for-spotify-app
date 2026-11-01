module Ignite.Api.Tests.DatabaseReadinessTests

open System
open System.IO
open System.Threading
open Ignite.Api
open Ignite.Infrastructure.Data
open Microsoft.EntityFrameworkCore
open Xunit

let private createContext (connectionString: string) =
    let options =
        DbContextOptionsBuilder<IgniteDbContext>()
            .UseSqlite(connectionString)
            .Options

    new IgniteDbContext(options)

[<Fact>]
let ``readiness is healthy for an available database`` () =
    task {
        use context = createContext "Data Source=:memory:"
        let! _ = context.Database.EnsureCreatedAsync()
        let! result = DatabaseReadiness.checkAsync context CancellationToken.None
        Assert.Equal(200, DatabaseReadiness.statusCode result)
    }

[<Fact>]
let ``readiness is unavailable for a missing database`` () =
    task {
        let path = Path.Combine(Path.GetTempPath(), $"missing-readiness-{Guid.NewGuid():N}.db")
        use context = createContext $"Data Source={path};Mode=ReadOnly"
        let! result = DatabaseReadiness.checkAsync context CancellationToken.None
        Assert.Equal(503, DatabaseReadiness.statusCode result)
    }

[<Fact>]
let ``readiness is unavailable for a corrupt database`` () =
    task {
        let path = Path.Combine(Path.GetTempPath(), $"corrupt-readiness-{Guid.NewGuid():N}.db")

        try
            File.WriteAllText(path, "not a sqlite database")
            use context = createContext $"Data Source={path};Mode=ReadOnly"
            let! result = DatabaseReadiness.checkAsync context CancellationToken.None
            Assert.Equal(503, DatabaseReadiness.statusCode result)
        finally
            if File.Exists(path) then
                File.Delete(path)
    }
