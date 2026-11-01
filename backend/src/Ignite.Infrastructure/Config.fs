namespace Ignite.Infrastructure.Spotify

open System

type SpotifyConfig() =
    static member SectionName = "Spotify"

    member val ClientId = "" with get, set
    member val ClientSecret = "" with get, set
    member val RedirectUri = "" with get, set

    static member DefaultScopes =
        [| "user-read-private"
           "playlist-read-private"
           "playlist-read-collaborative"
           "playlist-modify-public"
           "playlist-modify-private" |]

namespace Ignite.Infrastructure.Scraping

type CdlcScraperConfig() =
    static member SectionName = "CdlcScraper"

    member val BaseUrl = "https://ignition4.customsforge.com" with get, set
    member val SearchPath = "/search/advanced" with get, set
    member val LivewirePath = "/livewire/update" with get, set
    member val PageSize = 100 with get, set
    member val MaxRequestsPerSecond = 2 with get, set
    member val QueueLimit = 50 with get, set
    member val MaxRetryAttempts = 3 with get, set
    member val Username: string | null = null with get, set
    member val Password: string | null = null with get, set
    member val Cookies: string | null = null with get, set
