namespace Ignite.Infrastructure.Scraping

open System
open System.Collections.Generic
open System.IO
open System.Net
open System.Text.Json

[<AllowNullLiteral>]
type private CookieEntry() =
    member val Name = "" with get, set
    member val Value = "" with get, set
    member val Domain = "" with get, set
    member val Path = "/" with get, set
    member val Secure = false with get, set
    member val HttpOnly = false with get, set
    member val Expires = DateTime.MinValue with get, set

type CookiePersistence(container: CookieContainer, filePath: string) =
    static let knownDomains =
        [| Uri("https://customsforge.com")
           Uri("https://ignition4.customsforge.com") |]

    member _.Load() =
        try
            if File.Exists(filePath) then
                let json = File.ReadAllText(filePath)
                let entries = JsonSerializer.Deserialize<List<CookieEntry>>(json)

                if not (isNull entries) then
                    for entry in entries do
                        let cookie = Cookie(entry.Name, entry.Value, entry.Path, entry.Domain, Secure = entry.Secure, HttpOnly = entry.HttpOnly)

                        if entry.Expires > DateTime.UtcNow then
                            cookie.Expires <- entry.Expires

                        container.Add(cookie)
        with _ ->
            ()

    member _.Save() =
        try
            let entries = List<CookieEntry>()

            for domain in knownDomains do
                let cookies = container.GetCookies(domain)

                for cookie in cookies do
                    if not cookie.Expired then
                        let entry = CookieEntry()
                        entry.Name <- cookie.Name
                        entry.Value <- cookie.Value
                        entry.Domain <- cookie.Domain
                        entry.Path <- cookie.Path
                        entry.Secure <- cookie.Secure
                        entry.HttpOnly <- cookie.HttpOnly
                        entry.Expires <- cookie.Expires
                        entries.Add(entry)

            let dir = Path.GetDirectoryName(filePath)

            if not (isNull dir) then
                Directory.CreateDirectory(dir) |> ignore

            let json =
                JsonSerializer.Serialize(entries, JsonSerializerOptions(WriteIndented = true))

            File.WriteAllText(filePath, json)
        with _ ->
            ()
