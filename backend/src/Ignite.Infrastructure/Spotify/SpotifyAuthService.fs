namespace Ignite.Infrastructure.Spotify

open System
open System.Linq
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Interfaces
open Microsoft.Extensions.Logging
open Microsoft.Extensions.Options
open SpotifyAPI.Web

type SpotifyAuthService(config: IOptions<SpotifyConfig>, logger: ILogger<SpotifyAuthService>) =
    let config = config.Value

    interface ISpotifyAuthService with
        member _.GetAuthorizationUrl(state: string) =
            let loginRequest =
                LoginRequest(Uri(config.RedirectUri), config.ClientId, LoginRequest.ResponseType.Code,
                    Scope = SpotifyConfig.DefaultScopes,
                    State = state)

            loginRequest.ToUri().ToString()

        member _.ExchangeCodeAsync(code: string, cancellationToken: CancellationToken) =
            task {
                logger.LogInformation("Exchanging authorization code for tokens")

                let! response =
                    OAuthClient()
                        .RequestToken(
                            AuthorizationCodeTokenRequest(
                                config.ClientId,
                                config.ClientSecret,
                                code,
                                Uri(config.RedirectUri)
                            ),
                            cancellationToken
                        )

                return
                    SpotifyTokens(
                        response.AccessToken,
                        response.RefreshToken,
                        DateTime.UtcNow.AddSeconds(float response.ExpiresIn)
                    )
            }

        member _.RefreshTokenAsync(refreshToken: string, cancellationToken: CancellationToken) =
            task {
                logger.LogInformation("Refreshing Spotify access token")

                let! response =
                    OAuthClient()
                        .RequestToken(
                            AuthorizationCodeRefreshRequest(config.ClientId, config.ClientSecret, refreshToken),
                            cancellationToken
                        )

                let newRefreshToken =
                    if isNull response.RefreshToken then
                        refreshToken
                    else
                        response.RefreshToken

                return
                    SpotifyTokens(
                        response.AccessToken,
                        newRefreshToken,
                        DateTime.UtcNow.AddSeconds(float response.ExpiresIn)
                    )
            }

        member _.GetUserProfileAsync(accessToken: string, cancellationToken: CancellationToken) =
            task {
                let client = SpotifyClient(accessToken)
                let! profile = client.UserProfile.Current(cancellationToken)

                return
                    SpotifyUserProfile(
                        profile.Id,
                        (if isNull profile.DisplayName then profile.Id else profile.DisplayName),
                        (if isNull profile.Images || profile.Images.Count = 0 then
                             null
                         else
                             profile.Images.First().Url)
                    )
            }
