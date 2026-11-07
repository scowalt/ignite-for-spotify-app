# Privacy

The privacy notice explains what Ignite handles, why, where it goes, and the user's choices. Anyone can read it without signing in, and every page links to it from the footer.

## Sub-features

- `privacy-page` shows the `Privacy` heading, the `Last updated` date, and the notice's named regions in order.
- `privacy-footer` opens the notice from the footer `Privacy` link on every page.
- `privacy-contact` offers `Contact / report an issue` as a `mailto:` link in the footer.

## How to get to it (user POV)

- Open `/privacy`.
- Choose `Privacy` in the footer of any page.
- Choose `Privacy notice` under the Home hero.

## Driving it with ignite-verify

Preconditions:

- Baseline run from [the index](./README.md), `$V doctor` exits `0`.

- **Footer entry.** Run `$V browser goto /discover`, then `$V browser click --role link --name "Privacy" --exact`, then `$V browser wait --role heading --name "Privacy" --exact`. `$V browser url` ends with `/privacy`.
- **Content.** Run `$V browser snapshot --path privacy/01-privacy.aria.yml --role article`. The snapshot lists nine regions in order: `Information Ignite handles`, `How the information is used`, `Spotify access`, `Analytics and diagnostics`, `Cookies and browser storage`, `Services that process information`, `Retention`, `Your choices`, `Contact`. Run `$V browser text --text "Last updated"` and record the date it prints.
- **Proof.** Run `$V browser screenshot --path privacy/01-privacy.png --full`.
- **Contact.** Run `$V browser count --role link --name "Contact / report an issue"`. Prints `1`. Do not click it; it opens a mail client.

## Gotchas

- `--name "Privacy"` without `--exact` also matches `Privacy notice` on Home. The footer link lives in the `Support and legal` navigation.
- The notice is long. Use `--full` screenshots and scope ARIA snapshots to `--role article` so the evidence stays reviewable.
- Wording changes to the notice are legal content. A verification that only proves the page renders does not prove the wording is approved.
