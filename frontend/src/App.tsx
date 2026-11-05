import type { RouteSectionProps } from "@solidjs/router";
import { useLocation } from "@solidjs/router";
import { AlertDialog } from "@kobalte/core/alert-dialog";
import { createEffect, createSignal, Suspense, Show } from "solid-js";
import { authStore } from "./stores/authStore";
import GitHubStarButton from "./components/GitHubStarButton";
import { HeaderAuthSkeleton, PageSkeleton } from "./components/Skeleton";
import { applyPageMetadata } from "./lib/pageMetadata";

function App(props: RouteSectionProps) {
  const location = useLocation();
  const [isLogoutDialogOpen, setIsLogoutDialogOpen] = createSignal(false);
  let cancelLogoutButton: HTMLButtonElement | undefined;

  createEffect(() => {
    applyPageMetadata(location.pathname);
  });

  return (
    <div class="min-h-screen bg-gray-900 text-white">
      <header class="bg-spotify-black border-b border-gray-800 p-4">
        <div class="container mx-auto flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <a
            href="/"
            class="whitespace-nowrap text-xl font-bold text-spotify-green hover:text-green-400"
          >
            Ignite for Spotify
          </a>
          <nav class="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-2 text-sm sm:w-auto sm:justify-end sm:gap-6">
            <a href="/" class="whitespace-nowrap hover:text-spotify-green">
              Home
            </a>
            <a
              href="/match"
              class="whitespace-nowrap hover:text-spotify-green"
            >
              Match My Music
            </a>
            <a
              href="/discover"
              class="whitespace-nowrap hover:text-spotify-green"
            >
              Discover & Export
            </a>

            <GitHubStarButton />

            { }
            <Show
              when={!authStore.isLoading()}
              fallback={<HeaderAuthSkeleton />}
            >
              <Show
                when={authStore.isAuthenticated()}
                fallback={
                  <button
                    onClick={authStore.login}
                    class="bg-spotify-green hover:bg-green-500 text-black text-sm font-semibold py-1.5 px-4 rounded-full"
                  >
                    Login
                  </button>
                }
              >
                <div class="flex items-center gap-2">
                  <Show when={authStore.user()?.imageUrl}>
                    <img
                      src={authStore.user()!.imageUrl!}
                      alt="Profile"
                      class="w-8 h-8 rounded-full"
                    />
                  </Show>
                  <span class="hidden text-sm text-gray-300 lg:inline">
                    {authStore.user()?.displayName}
                  </span>
                  <AlertDialog
                    open={isLogoutDialogOpen()}
                    onOpenChange={setIsLogoutDialogOpen}
                    modal
                  >
                    <AlertDialog.Trigger
                      aria-label="Log out"
                      disabled={authStore.isLoggingOut()}
                      class="rounded-sm text-sm text-gray-400 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green focus-visible:ring-offset-2 focus-visible:ring-offset-spotify-black disabled:cursor-wait disabled:opacity-60"
                    >
                      Logout
                    </AlertDialog.Trigger>

                    <AlertDialog.Portal>
                      <AlertDialog.Overlay class="fixed inset-0 z-40 bg-black/70" />
                      <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
                        <AlertDialog.Content
                          onOpenAutoFocus={(event) => {
                            event.preventDefault();
                            cancelLogoutButton?.focus();
                          }}
                          class="w-full max-w-md rounded-xl bg-gray-800 p-6 shadow-2xl shadow-black/40 focus:outline-none"
                        >
                          <AlertDialog.Title class="text-xl font-semibold text-white">
                            Disconnect Spotify?
                          </AlertDialog.Title>
                          <AlertDialog.Description class="mt-3 text-sm leading-6 text-gray-300">
                            This signs you out, deletes your saved Match My Music
                            results from the live service, and removes Ignite's
                            stored Spotify tokens. Playlists already created in
                            Spotify stay there.
                          </AlertDialog.Description>

                          <Show when={authStore.error()}>
                            <p
                              role="alert"
                              class="mt-4 rounded-lg bg-red-950/70 px-3 py-2 text-sm text-red-200"
                            >
                              {authStore.error()} Your Spotify connection and
                              saved results are still intact. Try again.
                            </p>
                          </Show>

                          <div class="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                            <AlertDialog.CloseButton
                              ref={(element) => {
                                cancelLogoutButton = element;
                              }}
                              disabled={authStore.isLoggingOut()}
                              class="rounded-full px-5 py-2.5 text-sm font-semibold text-gray-200 transition-colors hover:bg-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green disabled:cursor-wait disabled:opacity-60"
                            >
                              Cancel
                            </AlertDialog.CloseButton>
                            <button
                              type="button"
                              onClick={authStore.logout}
                              disabled={authStore.isLoggingOut()}
                              aria-busy={authStore.isLoggingOut()}
                              class="rounded-full bg-red-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-800 disabled:cursor-wait disabled:opacity-60"
                            >
                              {authStore.isLoggingOut()
                                ? "Disconnecting…"
                                : "Disconnect & delete"}
                            </button>
                          </div>
                        </AlertDialog.Content>
                      </div>
                    </AlertDialog.Portal>
                  </AlertDialog>
                </div>
              </Show>
            </Show>
          </nav>
        </div>
      </header>

      <Show when={authStore.error() && !isLogoutDialogOpen()}>
        <div
          role="alert"
          aria-live="assertive"
          class="container mx-auto mt-4 rounded-lg border border-red-700 bg-red-950/70 px-4 py-3 text-sm text-red-200"
        >
          {authStore.error()}
        </div>
      </Show>

      <main class="container mx-auto p-4">
        <Suspense fallback={<PageSkeleton />}>
          {props.children}
        </Suspense>
      </main>

      <footer class="mt-8 border-t border-gray-800 px-4 py-6">
        <div class="container mx-auto flex flex-col items-center gap-3 text-center text-sm text-gray-400 sm:flex-row sm:justify-between sm:text-left">
          <p>Ignite for Spotify — Spotify playlists meet Rocksmith CDLC</p>
          <nav
            aria-label="Support and legal"
            class="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 sm:justify-end"
          >
            <a
              href="/privacy"
              class="rounded-sm text-gray-400 transition-colors hover:text-spotify-green focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green"
            >
              Privacy
            </a>
            <a
              href="mailto:privacy@igniteforspotify.com?subject=Ignite%20for%20Spotify%20support%20or%20issue"
              class="rounded-sm text-gray-400 transition-colors hover:text-spotify-green focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green"
            >
              Contact / report an issue
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}

export default App;
