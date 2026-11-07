# Discover export

From Discover search results, a user selects songs and, once signed in to Spotify, creates a Spotify playlist containing the selected songs that have a Spotify match.

## Sub-features

- `export-select` toggles a row's checkbox and updates the `Clear (<n>)` count.
- `export-select-all` selects every result on the page with `Select All`; `Clear (<n>)` empties the selection.
- `export-signed-out` shows `Login with Spotify to export your selection` and a `Login with Spotify` button when songs are selected and nobody is signed in.
- `export-form` shows `Export <n> Songs to Spotify` with Playlist Name (required), Description, and `Make playlist public` when signed in.
- `export-create` creates the playlist and shows `Playlist Created!`.

## How to get to it (user POV)

- On `/discover`, search, then select rows or choose `Select All`.

## Driving it with ignite-verify

Preconditions:

- Baseline run from [the index](./README.md), `$V doctor` exits `0`.
- `export-form` and `export-create` need a signed-in Spotify session. An isolated run cannot sign in (see [Spotify sign-in](./spotify-sign-in.md)); report both as failed with that reason.

- **Search.** Run `$V browser goto /discover`, `$V browser fill --placeholder "e.g., Metallica" --value "Metallica"`, then `$V browser wait --role cell --name "Enter Sandman"`.
- **Select one.** Check the first result row. Run `$V browser check --role checkbox --nth 5` (indexes 0–4 are the Lead, Rhythm, Bass, Vocals, and Has Spotify Match filters). `$V browser wait --role button --name "Clear (1)"` succeeds.
- **Select all.** Run `$V browser click --role button --name "Select All"` then `$V browser wait --role button --name "Clear (2)"`.
- **Signed-out gate.** Run `$V browser wait --text "Login with Spotify to export your selection"` and `$V browser snapshot --path discover-export/01-signed-out.aria.yml`. The snapshot shows `button "Login with Spotify"`; no `Playlist Name` field is present.
- **Clear.** Run `$V browser click --role button --name "Clear (2)"` then `$V browser wait-gone --text "Login with Spotify to export your selection"`.
- **Export form and create.** Not reachable. Report failed: `export-form`/`export-create` need Spotify sign-in; `GET /api/auth/login` returns 500 in an isolated run.

## Gotchas

- Row checkboxes are unnamed. `--role checkbox` also matches the five filter checkboxes above the table, so row checkboxes start at `--nth 5`. Confirm with the `Clear (<n>)` button rather than trusting the index.
- `Select All` selects only the current page of results.
- Selected songs without a Spotify match cannot land in a playlist; the export count in the form header is the selection size, not the exportable count.
- Choosing `Login with Spotify` navigates away to `/api/auth/login`, which fails in an isolated run and discards the selection.
