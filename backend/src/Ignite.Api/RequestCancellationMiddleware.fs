namespace Ignite.Api

open System
open System.Threading.Tasks
open Microsoft.AspNetCore.Http

module RequestCancellationMiddleware =
    [<Literal>]
    let ClientClosedRequestStatusCode = 499

    let invoke (context: HttpContext) (next: RequestDelegate) : Task =
        task {
            try
                do! next.Invoke(context)
            with
            | :? OperationCanceledException when context.RequestAborted.IsCancellationRequested ->
                if not context.Response.HasStarted then
                    context.Response.StatusCode <- ClientClosedRequestStatusCode
        }
