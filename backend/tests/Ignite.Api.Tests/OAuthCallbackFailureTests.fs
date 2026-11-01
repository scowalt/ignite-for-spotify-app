module Ignite.Api.Tests.OAuthCallbackFailureTests

open Ignite.Api
open SpotifyAPI.Web
open Xunit

[<Fact>]
let ``invalid Spotify authorization grants return an actionable retry redirect`` () =
    let redirect = OAuthCallbackFailure.tryGetRedirect (APIException("invalid_grant"))

    Assert.Equal(Some OAuthCallbackFailure.InvalidGrantRedirect, redirect)

[<Fact>]
let ``other Spotify authorization failures continue through the error path`` () =
    let redirect = OAuthCallbackFailure.tryGetRedirect (APIException("invalid_client"))

    Assert.Equal(None, redirect)
