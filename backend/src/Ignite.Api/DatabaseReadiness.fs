namespace Ignite.Api

open System
open System.Threading
open System.Threading.Tasks
open Ignite.Infrastructure.Data
open Microsoft.EntityFrameworkCore

type DatabaseReadinessResult =
    | Ready
    | Unavailable of error: Exception option

[<RequireQualifiedAccess>]
module DatabaseReadiness =
    let checkAsync (context: IgniteDbContext) (cancellationToken: CancellationToken) =
        task {
            try
                let! canConnect = context.Database.CanConnectAsync(cancellationToken)

                if canConnect then
                    let! _ = context.Database.ExecuteSqlRawAsync("SELECT 1;", cancellationToken)
                    return Ready
                else
                    return Unavailable None
            with
            | :? OperationCanceledException ->
                return raise (OperationCanceledException(cancellationToken))
            | ex -> return Unavailable(Some ex)
        }

    let statusCode result =
        match result with
        | Ready -> 200
        | Unavailable _ -> 503
