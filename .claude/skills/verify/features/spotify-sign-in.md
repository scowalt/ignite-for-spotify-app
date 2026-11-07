# Spotify sign-in

Account-backed features start with Spotify sign-in. A signed-out user sees login buttons in several places; a failed or expired callback brings the user back to Home with an alert; a signed-in user sees their profile in the header.

## Sub-features

- `signin-header` sends the user to Spotify from the header `Login` button on every page.
- `signin-home-cta` sends the user to Spotify from `Get Started with Spotify` on Home.
- `signin-gates` sends the user to Spotify from `Login with Spotify` on Match My Music and in the Discover export panel.
- `signin-expired` shows the alert `Your Spotify sign-in link expired. Please try again.` after the callback redirects to `/?error=auth_expired`.
- `signin-session` replaces `Login` with the signed-in profile and a logout control.

## How to get to it (user POV)

- Choose `Login` in the header.
- Choose `Get Started with Spotify` on Home.
- Choose `Login with Spotify` on `/match`, or in the export panel on `/discover` after selecting songs.
- Return from Spotify through an expired or reused authorization link, which lands on `/?error=auth_expired`.

## Driving it with ignite-verify

Preconditions:

- Baseline run from [the index](./README.md), `$V doctor` exits `0`.
- Reaching Spotify needs `Spotify__ClientId`, `Spotify__ClientSecret`, and a `Spotify__RedirectUri` that Spotify has registered for this run's origin. The isolated run has none, and Doppler `dev` registers only the production callback. Every journey past the redirect is therefore failed with that reason.

- **Signed out.** Run `$V api GET /api/auth/session`. Prints `HTTP 401`. Run `$V browser goto /` and `$V browser wait --role button --name "Login" --exact`.
- **Header login.** Run `$V browser click --role button --name "Login" --exact` then `$V browser wait-url "/api/auth/login"`. Run `$V browser screenshot --path spotify-sign-in/01-login-500.png`. Expected in an isolated run: the ASP.NET developer error page for `String is empty or null (Parameter 'clientId')`. Report `signin-header` as failed with that message; a correctly configured instance would redirect to `accounts.spotify.com`.
- **Home CTA.** Run `$V browser goto /`, `$V browser click --role button --name "Get Started with Spotify"`, `$V browser wait-url "/api/auth/login"`. Same outcome and report as the header.
- **Gates.** Run `$V browser goto /match`, `$V browser click --role button --name "Login with Spotify"`, `$V browser wait-url "/api/auth/login"`. Same outcome and report. The Discover export gate is covered in [Discover export](./discover-export.md).
- **Expired link.** Run `$V browser goto "/?error=auth_expired"` then `$V browser wait --role alert`. `$V browser text --role alert` prints `Your Spotify sign-in link expired. Please try again.` Run `$V browser screenshot --path spotify-sign-in/02-expired.png`.
- **Session.** Not reachable. Report `signin-session` as failed: no Spotify sign-in in an isolated run.

## Gotchas

- `--name "Login"` without `--exact` also matches `Login with Spotify`.
- The login request leaves the SPA, so later commands act on the error page until the next `goto`.
- Do not insert rows into `user_sessions` or set a forged `session_id` cookie to fake a session. That bypasses the real user path and every Spotify call behind it still fails.
- The `/api/auth/login` 500 is a property of the isolated run, not a regression. A 500 with any other message, or a 500 on a run that has Spotify credentials, is a real failure.
