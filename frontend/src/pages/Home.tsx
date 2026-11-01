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
    <div class="space-y-16 py-8">
      { }
      <section class="text-center max-w-3xl mx-auto">
        <h1 class="text-4xl md:text-5xl font-bold mb-4">
          Find Your Spotify Music in Rocksmith
        </h1>
        <p class="text-lg text-gray-400 mb-8 max-w-2xl mx-auto">
          Connect your Spotify account and instantly discover which songs in your
          playlists have community-created Rocksmith content ready to download.
        </p>
        <div class="flex flex-col sm:flex-row gap-4 justify-center items-center">
          <Show when={!authStore.isLoading()}>
            <Show
              when={authStore.isAuthenticated()}
              fallback={
                <div class="flex max-w-sm flex-col items-center gap-2">
                  <button
                    onClick={authStore.login}
                    class="rounded-full bg-spotify-green px-8 py-3 text-lg font-semibold text-black transition hover:bg-green-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
                  >
                    Get Started with Spotify
                  </button>
                  <p class="text-xs leading-5 text-gray-400">
                    Before connecting, see how Ignite handles your data in the{" "}
                    <a
                      href="/privacy"
                      class="text-gray-300 underline decoration-gray-600 underline-offset-4 transition-colors hover:text-spotify-green focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green"
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
                class="bg-spotify-green hover:bg-green-400 text-black font-semibold px-8 py-3 rounded-full text-lg transition"
              >
                Match My Music
              </a>
            </Show>
          </Show>
          <a
            href="/discover"
            class="text-gray-400 hover:text-white transition underline underline-offset-4"
          >
            Browse CDLC Database
          </a>
        </div>
      </section>

      { }
      <section class="max-w-3xl mx-auto">
        <div class="bg-gray-800 rounded-lg p-6 grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          <div>
            <div class="text-2xl font-bold text-white">
              <Show
                when={statsQuery.data}
                fallback={<SkeletonText class="h-7 w-20 mx-auto" />}
              >
                {formatNumber(statsQuery.data!.totalSongs)}
              </Show>
            </div>
            <div class="text-sm text-gray-400 mt-1">CDLC Songs</div>
          </div>
        </div>
      </section>

      { }
      <section class="max-w-3xl mx-auto">
        <h2 class="text-2xl font-bold text-center mb-8">How It Works</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div class="text-center">
            <div class="w-10 h-10 rounded-full bg-spotify-green text-black font-bold text-lg flex items-center justify-center mx-auto mb-3">
              1
            </div>
            <h3 class="font-semibold mb-1">Connect Spotify</h3>
            <p class="text-sm text-gray-400">
              Log in with your Spotify account
            </p>
          </div>
          <div class="text-center">
            <div class="w-10 h-10 rounded-full bg-spotify-green text-black font-bold text-lg flex items-center justify-center mx-auto mb-3">
              2
            </div>
            <h3 class="font-semibold mb-1">Pick a Playlist</h3>
            <p class="text-sm text-gray-400">
              Select any playlist from your library
            </p>
          </div>
          <div class="text-center">
            <div class="w-10 h-10 rounded-full bg-spotify-green text-black font-bold text-lg flex items-center justify-center mx-auto mb-3">
              3
            </div>
            <h3 class="font-semibold mb-1">Download Matches</h3>
            <p class="text-sm text-gray-400">
              Get CDLC for songs you already love
            </p>
          </div>
        </div>
      </section>

      { }
      <section class="max-w-2xl mx-auto">
        <div class="bg-gray-800/50 rounded-lg p-6 text-left">
          <h3 class="text-lg font-semibold text-spotify-green mb-2">
            What is CDLC?
          </h3>
          <p class="text-gray-400 text-sm">
            CDLC (Custom Downloadable Content) are community-created songs for
            Rocksmith, a music video game that helps you learn guitar and bass.
            The CustomsForge community hosts thousands of custom songs you can
            play in Rocksmith.
          </p>
        </div>
      </section>

      { }
      <section class="max-w-4xl mx-auto">
        <div class="grid md:grid-cols-2 gap-6">
          <a
            href="/match"
            class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-700 transition border border-gray-700 hover:border-spotify-green"
          >
            <h3 class="text-xl font-semibold text-spotify-green mb-2">
              Match My Music
            </h3>
            <p class="text-gray-400">
              See which of your favorite Spotify songs are available as
              Rocksmith CDLC — no more guessing what's out there.
            </p>
          </a>

          <a
            href="/discover"
            class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-700 transition border border-gray-700 hover:border-spotify-green"
          >
            <h3 class="text-xl font-semibold text-spotify-green mb-2">
              Discover & Export
            </h3>
            <p class="text-gray-400">
              Browse the full CDLC database and create Spotify playlists to
              preview songs before you download.
            </p>
          </a>
        </div>
      </section>
    </div>
  );
}
