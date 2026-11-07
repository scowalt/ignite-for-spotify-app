const supportEmail = "privacy@igniteforspotify.com";
const supportHref = `mailto:${supportEmail}`;

const linkClass = "privacy-link focus-ring";

export default function Privacy() {
  return (
    <div class="privacy-page">
      <header class="privacy-header">
        <h1 class="privacy-title">
          Privacy
        </h1>
        <p class="privacy-intro">
          This notice explains what Ignite for Spotify handles when you use the
          service, why it is needed, where it goes, and the choices available to
          you.
        </p>
        <p class="privacy-updated">Last updated August 16, 2026</p>
      </header>

      <article class="privacy-body">
        <section aria-labelledby="information-heading">
          <h2
            id="information-heading"
            class="privacy-heading"
          >
            Information Ignite handles
          </h2>
          <p>
            You can browse public CDLC information without connecting Spotify.
            When you connect Spotify, Ignite receives and processes the data
            needed to provide account-backed features:
          </p>
          <ul class="privacy-list">
            <li>
              Your Spotify account ID, display name, profile image, access and
              refresh tokens, and token expiration time.
            </li>
            <li>
              Playlist identifiers, names, descriptions, images, and track
              metadata needed to display, match, and export playlists.
            </li>
            <li>
              The latest completed Match My Music result for each playlist you
              search, including track metadata, matching CDLC, summary counts,
              and the time it was generated.
            </li>
            <li>
              Playlist names, descriptions, visibility choices, and selected
              tracks that you submit when creating a playlist in Spotify.
            </li>
          </ul>
          <p>
            Ignite does not receive your Spotify password or payment details.
          </p>
        </section>

        <section
          aria-labelledby="use-heading"
          class="privacy-section"
        >
          <h2
            id="use-heading"
            class="privacy-heading"
          >
            How the information is used
          </h2>
          <p>Ignite uses this information to:</p>
          <ul class="privacy-list">
            <li>Keep you signed in and refresh your Spotify connection.</li>
            <li>
              Read playlists and compare their tracks with the Rocksmith CDLC
              catalog.
            </li>
            <li>
              Preserve your latest completed match results so you can revisit
              them without automatically searching again.
            </li>
            <li>Create the Spotify playlists you explicitly request.</li>
            <li>
              Understand feature usage, diagnose failures, secure the service,
              and improve performance and reliability.
            </li>
          </ul>
        </section>

        <section
          aria-labelledby="spotify-heading"
          class="privacy-section"
        >
          <h2
            id="spotify-heading"
            class="privacy-heading"
          >
            Spotify access
          </h2>
          <p>
            Ignite asks Spotify for permission to read your private and
            collaborative playlists, read the basic private profile needed to
            identify your connection, and create or modify public and private
            playlists. Spotify shows these permissions before you approve the
            connection.
          </p>
          <p>
            Removing Ignite locally does not revoke it from Spotify's connected
            apps list. You can also remove access from Spotify by following the
            instructions on Spotify's{" "}
            <a
              href="https://support.spotify.com/us/article/spotify-on-other-apps/"
              class={linkClass}
            >
              connected-app support page
            </a>
            .
          </p>
        </section>

        <section
          aria-labelledby="analytics-heading"
          class="privacy-section"
        >
          <h2
            id="analytics-heading"
            class="privacy-heading"
          >
            Analytics and diagnostics
          </h2>
          <p>
            Ignite uses PostHog for product analytics. It records page visits,
            feature actions, performance information, and production session
            replays. After you sign in, the analytics profile is associated
            with your Spotify account ID, display name, and profile image.
            Feature events can include playlist identifiers, playlist names,
            search filters, match totals, export details, and download choices.
          </p>
          <p>
            Replay inputs are masked. Browser console output and network request
            or response headers and bodies are not recorded, and query strings
            and page fragments are removed from captured URLs.
          </p>
          <p>
            Ignite also sends application errors to GlitchTip and operational
            logs and metrics to Grafana Cloud. These records can include error
            details, request paths, timestamps, browser or device information,
            network addresses, response status, and timing information.
          </p>
        </section>

        <section
          aria-labelledby="storage-heading"
          class="privacy-section"
        >
          <h2
            id="storage-heading"
            class="privacy-heading"
          >
            Cookies and browser storage
          </h2>
          <p>
            Ignite sets a secure, HTTP-only session cookie after Spotify login.
            It is limited to same-site use and expires 30 days after it is
            issued or renewed. Blocking it prevents signed-in features from
            working.
          </p>
          <p>
            PostHog uses cookies or similar browser storage for analytics and
            session continuity. You can block or clear browser storage using
            your browser settings, although doing so can reset analytics
            identity and disable or disrupt some site behavior.
          </p>
        </section>

        <section
          aria-labelledby="sharing-heading"
          class="privacy-section"
        >
          <h2
            id="sharing-heading"
            class="privacy-heading"
          >
            Services that process information
          </h2>
          <p>
            Ignite uses Spotify for account and playlist features, PostHog for
            analytics and session replay, GlitchTip for error monitoring,
            Grafana Cloud for logs and metrics, and Cloudflare for network
            delivery and encrypted database backups. Each service processes
            only the information sent to support those functions and applies
            its own privacy and retention terms.
          </p>
          <p>
            CDLC download links lead to CustomsForge, an independent service.
            Information you provide after following an external link is handled
            by that destination rather than Ignite.
          </p>
        </section>

        <section
          aria-labelledby="retention-heading"
          class="privacy-section"
        >
          <h2
            id="retention-heading"
            class="privacy-heading"
          >
            Retention
          </h2>
          <ul class="privacy-list">
            <li>
              Server-side session information and Spotify tokens remain until
              you log out or request deletion.
            </li>
            <li>
              A saved match snapshot remains until it is replaced by a complete
              refresh, you log out, or you request deletion.
            </li>
            <li>
              The encrypted database backup schedule keeps 30 daily and 12
              monthly snapshots. Deleted live data ages out of those backups as
              the snapshots expire, which can take up to 12 months.
            </li>
            <li>
              Web access logs rotate by size and retain up to five 10 MB files.
            </li>
            <li>
              Analytics and diagnostic records follow the retention configured
              with their providers. Contact Ignite for current details or to
              request removal of account-linked records.
            </li>
          </ul>
        </section>

        <section
          aria-labelledby="choices-heading"
          class="privacy-section"
        >
          <h2
            id="choices-heading"
            class="privacy-heading"
          >
            Your choices
          </h2>
          <p>
            Selecting Logout and confirming the action disconnects your Spotify
            account from Ignite, deletes the live session and Spotify tokens,
            and deletes your saved Match My Music results. This does not delete
            playlists previously created in your Spotify account, immediately
            remove data from aging backups, or automatically erase provider-side
            analytics and diagnostic records.
          </p>
          <p>
            For access questions or deletion of remaining account-linked
            records, email{" "}
            <a href={supportHref} class={linkClass}>
              {supportEmail}
            </a>
            . Include enough information to identify your connection, but do
            not send passwords or Spotify access tokens.
          </p>
        </section>

        <section
          aria-labelledby="contact-heading"
          class="privacy-section"
        >
          <h2
            id="contact-heading"
            class="privacy-heading"
          >
            Contact
          </h2>
          <p>
            Ignite for Spotify operates this service. Send privacy questions,
            support requests, or issue reports to{" "}
            <a href={supportHref} class={linkClass}>
              {supportEmail}
            </a>
            .
          </p>
        </section>
      </article>
    </div>
  );
}
