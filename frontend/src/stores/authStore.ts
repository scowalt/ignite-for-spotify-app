import { createSignal, createEffect } from "solid-js";
import type { AuthSession } from "../types/api";
import { auth } from "../lib/api";
import { analytics } from "../lib/analytics";

const [session, setSession] = createSignal<AuthSession | null>(null);
const [isLoading, setIsLoading] = createSignal(true);
const [isLoggingOut, setIsLoggingOut] = createSignal(false);
const [error, setError] = createSignal<string | null>(null);

const isAuthenticated = () => session() !== null;
const user = () => session()?.profile ?? null;

const isSessionExpired = () => {
  const currentSession = session();
  if (!currentSession) return true;

  const expiresAt = new Date(currentSession.expiresAt);
  return expiresAt <= new Date();
};

function getOAuthCallbackError(search: string) {
  const error = new URLSearchParams(search).get("error");

  if (error === "auth_expired") {
    return "Your Spotify sign-in link expired. Please try again.";
  }

  return null;
}

async function initAuth() {
  setIsLoading(true);
  setError(getOAuthCallbackError(window.location.search));

  try {
    const currentSession = await auth.getSession();
    setSession(currentSession);
    if (currentSession?.profile) {
      analytics.loginCompleted(currentSession.profile);
    }
  } catch (err) {
    if (err instanceof Error && "status" in err && err.status === 401) {
      setSession(null);
    } else {
      setError(err instanceof Error ? err.message : "Failed to check auth");
    }
  } finally {
    setIsLoading(false);
  }
}

function login() {
  analytics.loginInitiated();
  window.location.href = auth.getLoginUrl();
}

async function logout() {
  if (isLoggingOut()) return;

  setIsLoggingOut(true);
  setError(null);

  try {
    await auth.logout();
    setSession(null);

    try {
      analytics.logout();
    } catch {
      void 0;
    }

    window.location.replace("/");
  } catch (err) {
    setError(err instanceof Error ? err.message : "Failed to logout");
  } finally {
    setIsLoggingOut(false);
  }
}

async function refreshIfNeeded() {
  if (!isSessionExpired()) return;

  try {
    const newSession = await auth.refresh();
    setSession(newSession);
  } catch {
    setSession(null);
    setError("Session expired, please login again");
  }
}

createEffect(() => {
  const currentSession = session();
  if (!currentSession) return;

  const expiresAt = new Date(currentSession.expiresAt);
  const now = new Date();
  const msUntilExpiry = expiresAt.getTime() - now.getTime();

  const refreshTime = msUntilExpiry - 5 * 60 * 1000;

  if (refreshTime > 0) {
    const timer = setTimeout(refreshIfNeeded, refreshTime);
    return () => clearTimeout(timer);
  }
});

export const authStore = {
  session,
  isLoading,
  isLoggingOut,
  error,
  isAuthenticated,
  user,

  initAuth,
  login,
  logout,
  refreshIfNeeded,
};
