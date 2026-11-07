import { Show } from "solid-js";
import { createQuery } from "@tanstack/solid-query";
import { authStore } from "../stores/authStore";
import { songs } from "../lib/api";
import { SkeletonText } from "../components/Skeleton";

export default function Home() {
  const statsQuery = createQuery(() => ({
    queryKey: ["db-stats"],
    queryFn: () => songs.getStats(),
  }));

  const formatNumber = (n: number) => n.toLocaleString();

  return (
    <div class="home">
      { }
      <section class="home-hero">
        <h1 class="home-title">
          Find Your Spotify Music in Rocksmith
        </h1>
        <p class="home-lede">
          Connect your Spotify account and instantly discover which songs in your
          playlists have community-created Rocksmith content ready to download.
        </p>
        <div class="home-actions">
          <Show when={!authStore.isLoading()}>
            <Show
              when={authStore.isAuthenticated()}
              fallback={
                <div class="home-get-started">
                  <button
                    onClick={authStore.login}
                    class="button-hero home-get-started-button focus-ring"
                  >
                    Get Started with Spotify
                  </button>
                  <p class="home-privacy-note">
                    Before connecting, see how Ignite handles your data in the{" "}
                    <a
                      href="/privacy"
                      class="home-privacy-link focus-ring"
                    >
                      Privacy notice
                    </a>
                    .
                  </p>
                </div>
              }
            >
              <a
                href="/match"
                class="button-hero"
              >
                Match My Music
              </a>
            </Show>
          </Show>
          <a
            href="/discover"
            class="home-browse-link"
          >
            Browse CDLC Database
          </a>
        </div>
      </section>

      { }
      <section class="home-section">
        <div class="panel home-stats">
          <div>
            <div class="home-stat-value">
              <Show
                when={statsQuery.data}
                fallback={<SkeletonText class="skeleton-home-stat" />}
              >
                {formatNumber(statsQuery.data!.totalSongs)}
              </Show>
            </div>
            <div class="home-stat-label">CDLC Songs</div>
          </div>
        </div>
      </section>

      { }
      <section class="home-section">
        <h2 class="home-heading">How It Works</h2>
        <div class="home-steps">
          <div class="home-step">
            <div class="home-step-number">
              1
            </div>
            <h3 class="home-step-title">Connect Spotify</h3>
            <p class="home-step-text">
              Log in with your Spotify account
            </p>
          </div>
          <div class="home-step">
            <div class="home-step-number">
              2
            </div>
            <h3 class="home-step-title">Pick a Playlist</h3>
            <p class="home-step-text">
              Select any playlist from your library
            </p>
          </div>
          <div class="home-step">
            <div class="home-step-number">
              3
            </div>
            <h3 class="home-step-title">Download Matches</h3>
            <p class="home-step-text">
              Get CDLC for songs you already love
            </p>
          </div>
        </div>
      </section>

      { }
      <section class="home-section-narrow">
        <div class="home-explainer">
          <h3 class="home-explainer-title">
            What is CDLC?
          </h3>
          <p class="home-explainer-text">
            CDLC (Custom Downloadable Content) are community-created songs for
            Rocksmith, a music video game that helps you learn guitar and bass.
            The CustomsForge community hosts thousands of custom songs you can
            play in Rocksmith.
          </p>
        </div>
      </section>

      { }
      <section class="home-section-wide">
        <div class="home-features">
          <a
            href="/match"
            class="home-feature"
          >
            <h3 class="home-feature-title">
              Match My Music
            </h3>
            <p class="home-feature-text">
              See which of your favorite Spotify songs are available as
              Rocksmith CDLC — no more guessing what's out there.
            </p>
          </a>

          <a
            href="/discover"
            class="home-feature"
          >
            <h3 class="home-feature-title">
              Discover & Export
            </h3>
            <p class="home-feature-text">
              Browse the full CDLC database and create Spotify playlists to
              preview songs before you download.
            </p>
          </a>
        </div>
      </section>
    </div>
  );
}
