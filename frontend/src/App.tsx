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
    <div class="app-shell">
      <header class="site-header">
        <div class="container site-header-inner">
          <a
            href="/"
            class="site-brand"
          >
            Ignite for Spotify
          </a>
          <nav class="site-nav">
            <a href="/" class="site-nav-link">
              Home
            </a>
            <a
              href="/match"
              class="site-nav-link"
            >
              Match My Music
            </a>
            <a
              href="/discover"
              class="site-nav-link"
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
                    class="header-login"
                  >
                    Login
                  </button>
                }
              >
                <div class="header-account">
                  <Show when={authStore.user()?.imageUrl}>
                    <img
                      src={authStore.user()!.imageUrl!}
                      alt="Profile"
                      class="header-avatar"
                    />
                  </Show>
                  <span class="header-user-name">
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
                      class="header-logout focus-ring"
                    >
                      Logout
                    </AlertDialog.Trigger>

                    <AlertDialog.Portal>
                      <AlertDialog.Overlay class="dialog-overlay" />
                      <div class="dialog-positioner">
                        <AlertDialog.Content
                          onOpenAutoFocus={(event) => {
                            event.preventDefault();
                            cancelLogoutButton?.focus();
                          }}
                          class="dialog"
                        >
                          <AlertDialog.Title class="dialog-title">
                            Disconnect Spotify?
                          </AlertDialog.Title>
                          <AlertDialog.Description class="dialog-description">
                            This signs you out, deletes your saved Match My Music
                            results from the live service, and removes Ignite's
                            stored Spotify tokens. Playlists already created in
                            Spotify stay there.
                          </AlertDialog.Description>

                          <Show when={authStore.error()}>
                            <p
                              role="alert"
                              class="dialog-error"
                            >
                              {authStore.error()} Your Spotify connection and
                              saved results are still intact. Try again.
                            </p>
                          </Show>

                          <div class="dialog-actions">
                            <AlertDialog.CloseButton
                              ref={(element) => {
                                cancelLogoutButton = element;
                              }}
                              disabled={authStore.isLoggingOut()}
                              class="dialog-cancel focus-ring"
                            >
                              Cancel
                            </AlertDialog.CloseButton>
                            <button
                              type="button"
                              onClick={authStore.logout}
                              disabled={authStore.isLoggingOut()}
                              aria-busy={authStore.isLoggingOut()}
                              class="dialog-confirm focus-ring"
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
          class="container app-alert"
        >
          {authStore.error()}
        </div>
      </Show>

      <main class="container site-main">
        <Suspense fallback={<PageSkeleton />}>
          {props.children}
        </Suspense>
      </main>

      <footer class="site-footer">
        <div class="container site-footer-inner">
          <p>Ignite for Spotify — Spotify playlists meet Rocksmith CDLC</p>
          <nav
            aria-label="Support and legal"
            class="site-footer-nav"
          >
            <a
              href="/privacy"
              class="site-footer-link focus-ring"
            >
              Privacy
            </a>
            <a
              href="mailto:privacy@igniteforspotify.com?subject=Ignite%20for%20Spotify%20support%20or%20issue"
              class="site-footer-link focus-ring"
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
