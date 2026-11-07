# Discover search

Discover & Export lets anyone, signed in or not, see catalog totals and search the Rocksmith CDLC catalog by artist, title, album, and instrument parts, optionally limited to songs that already have a Spotify match.

## Sub-features

- `discover-stats` shows Total Songs, With Spotify Match, and Match Rate for the whole catalog.
- `discover-idle` shows no results until a text filter or a part checkbox is set.
- `discover-text-filter` narrows results by artist, title, or album substring as the user types.
- `discover-spotify-filter` hides songs without a Spotify match while `Has Spotify Match` is checked, and shows every song when it is unchecked.
- `discover-part-filter` narrows results to songs that have every checked part (Lead, Rhythm, Bass, Vocals).
- `discover-empty` shows `No songs found matching your criteria.` when nothing matches.
- `discover-rows` shows artist, title, album, part badges, and a Spotify ✓ or `None` for each result, with a `Results (<n> songs)` count.

## How to get to it (user POV)

- Open `/discover` directly.
- Choose `Discover & Export` in the header navigation from any page.
- Choose the `Discover & Export` card or `Browse CDLC Database` on Home.

## Driving it with ignite-verify

Preconditions:

- Baseline run from [the index](./README.md), `$V doctor` exits `0`.
- The fixture catalog is unchanged: `$V sql "select count(*) as n from songs"` prints `[{"n":6}]`.

- **Open.** Run `$V browser goto /discover` then `$V browser wait --role heading --name "Discover & Export"`. The page heading is visible.
- **Stats.** Run `$V browser snapshot --path discover-search/00-initial.aria.yml`. The snapshot lists `Total Songs` `6`, `With Spotify Match` `4`, `Match Rate` `66.7%`, and `checkbox "Has Spotify Match" [checked]`.
- **Idle.** Run `$V browser click --role button --name "Search" --exact` then `$V browser count --role table`. Prints `0`; no search runs without a text filter or part checkbox.
- **Artist filter.** Type `Metallica` into Artist. Run `$V browser fill --placeholder "e.g., Metallica" --value "Metallica"` then `$V browser wait --role cell --name "Enter Sandman"`. Run `$V browser text --role heading --name "Results"`: prints `Results (2 songs)`. `$V browser count --role row` prints `3` (header plus `Enter Sandman`, `Nothing Else Matters`). `One` is absent because it has no Spotify match.
- **Proof (matched).** Run `$V browser snapshot --path discover-search/01-metallica-matched.aria.yml --role table` and `$V browser screenshot --path discover-search/01-metallica-matched.png --full`.
- **Spotify filter off.** Uncheck `Has Spotify Match`. Run `$V browser uncheck --role checkbox --name "Has Spotify Match"` then `$V browser wait --role cell --name "One" --exact`. `Results (3 songs)`; `$V browser text --role row --name "Metallica One"` ends with `None`.
- **Proof (all).** Run `$V browser snapshot --path discover-search/02-metallica-all.aria.yml --role table` and `$V browser screenshot --path discover-search/02-metallica-all.png --full`.
- **Second view.** Run `$V sql "select title, spotify_track_id is not null as matched from songs where artist like '%Metallica%' order by title"`. Three rows, with `One` the only `matched: 0`, matching the table.
- **Part filter.** Clear Artist and check Vocals. Run `$V browser fill --placeholder "e.g., Metallica" --value ""` then `$V browser check --role checkbox --name "Vocals" --exact`, then `$V browser wait --role cell --name "Everlong"`. `Results (1 songs)` with the single row `Foo Fighters Everlong`.
- **Album filter.** Uncheck Vocals and type `Nevermind` into Album. Run `$V browser uncheck --role checkbox --name "Vocals" --exact`, `$V browser fill --placeholder "e.g., Black Album" --value "Nevermind"`, then `$V browser wait --role cell --name "Come as You Are"`. The row's Spotify cell reads `None`, proving the Spotify filter is still off.
- **Empty state.** Type `volcano` into Album. Run `$V browser fill --placeholder "e.g., Black Album" --value "volcano"` then `$V browser wait --text "No songs found matching your criteria."`. Run `$V browser screenshot --path discover-search/03-empty.png --full`.

## Gotchas

- Results update as the user types; the `Search` button only submits the form. Wait for a result cell or the empty message rather than clicking `Search` and reading immediately.
- `Has Spotify Match` alone does not start a search. Set a text filter or a part checkbox first.
- Unchecking `Has Spotify Match` removes the filter. It does not switch to "only songs without a match".
- Without `--exact`, `--name` is a case-insensitive substring match, so `--name "One"` would also match any cell containing "one" once the seed grows. Keep `--exact` on short titles.
- The results heading pluralizes literally: one result reads `Results (1 songs)`.
- Results page at 50 songs. The fixture catalog never shows `Previous`/`Next`; proving pagination needs more than 50 matching rows in `seed.sql`, and its absence is a failed precondition, not a pass.
- `goto` reloads the page and resets every filter. Start each journey with `goto /discover` rather than relying on the previous recipe's filters.
