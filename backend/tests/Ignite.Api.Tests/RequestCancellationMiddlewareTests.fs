module Ignite.Api.Tests.RequestCancellationMiddlewareTests

open System.Threading
open System.Threading.Tasks
open Ignite.Api
open Microsoft.AspNetCore.Http
open Xunit

[<Fact>]
let ``client cancellation is handled without surfacing a server error`` () =
    task {
        use cancellation = new CancellationTokenSource()
        cancellation.Cancel()

        let context = DefaultHttpContext()
        context.RequestAborted <- cancellation.Token

        let next =
            RequestDelegate(fun _ ->
                Task.FromException(TaskCanceledException("The request was canceled.")))

        do! RequestCancellationMiddleware.invoke context next

        Assert.Equal(
            RequestCancellationMiddleware.ClientClosedRequestStatusCode,
            context.Response.StatusCode
        )
    }

[<Fact>]
let ``server cancellation remains visible`` () =
    task {
        let context = DefaultHttpContext()

        let next =
            RequestDelegate(fun _ ->
                Task.FromException(TaskCanceledException("The database timed out.")))

        let! caught =
            Assert.ThrowsAsync<TaskCanceledException>(fun () ->
                RequestCancellationMiddleware.invoke context next)

        Assert.Equal("The database timed out.", caught.Message)
    }
