# Home

The landing page explains what Ignite does, shows how many CDLC songs the catalog holds, and routes the user to sign in, Match My Music, Discover & Export, or the privacy notice.

## Sub-features

- `home-hero` shows the heading `Find Your Spotify Music in Rocksmith` and the `Get Started with Spotify` button.
- `home-count` shows the catalog size as `<n> CDLC Songs`.
- `home-browse` opens Discover & Export from `Browse CDLC Database`.
- `home-cards` opens Match My Music and Discover & Export from the feature cards.
- `home-nav` reaches Home, Match My Music, and Discover & Export from the header on every page, and Home from the `Ignite for Spotify` logo.
- `home-privacy-link` opens the privacy notice from the `Privacy notice` link under the hero.

## How to get to it (user POV)

- Open `/`.
- Choose `Home` or the `Ignite for Spotify` logo in the header.

## Driving it with ignite-verify

Preconditions:

- Baseline run from [the index](./README.md), `$V doctor` exits `0`.

- **Open.** Run `$V browser goto /` then `$V browser wait --role heading --name "Find Your Spotify Music in Rocksmith"`.
- **Count.** Run `$V browser wait --text "CDLC Songs" --exact`, then `$V browser snapshot --path home/01-home.aria.yml` and `$V browser screenshot --path home/01-home.png --full`. The snapshot contains `text: 6 CDLC Songs`. Second view: `$V api GET /api/songs/stats` prints `"totalSongs":6`.
- **Browse.** Run `$V browser click --role link --name "Browse CDLC Database"` then `$V browser wait --role heading --name "Discover & Export" --exact`. `$V browser url` ends with `/discover`.
- **Cards.** Run `$V browser goto /`, `$V browser click --role link --name "Match My Music See which"`, `$V browser wait-url "/match$"`. Then `$V browser goto /`, `$V browser click --role link --name "Discover & Export Browse the full"`, `$V browser wait-url "/discover$"`.
- **Header nav.** From `/discover`, run `$V browser click --role link --name "Ignite for Spotify" --exact` then `$V browser wait-url "/$"`. Repeat with `--name "Home" --exact`.
- **Privacy link.** Run `$V browser goto /`, `$V browser click --role link --name "Privacy notice"`, `$V browser wait --role heading --name "Privacy" --exact`.

## Gotchas

- The card links' accessible names include their description text. Use a prefix such as `Match My Music See which`; the bare name `Match My Music` also matches the header link.
- The count and its `CDLC Songs` label are separate elements, so `--text "6 CDLC Songs"` never matches. Wait for the label, then read the count from the ARIA snapshot. The label appears only after the stats request resolves.
- The header's GitHub star button fetches the star count from GitHub through the API. Its label changes with network access and GitHub's answer, so never assert on the star count.
- `Get Started with Spotify` belongs to [Spotify sign-in](./spotify-sign-in.md).
