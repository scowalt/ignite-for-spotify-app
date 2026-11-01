namespace Ignite.Api

open System
open SpotifyAPI.Web

module OAuthCallbackFailure =
    [<Literal>]
    let InvalidGrantRedirect = "/?error=auth_expired"

    let tryGetRedirect (error: exn) =
        match error with
        | :? APIException as spotifyException when
            String.Equals(spotifyException.Message, "invalid_grant", StringComparison.OrdinalIgnoreCase) ->
            Some InvalidGrantRedirect
        | _ -> None
