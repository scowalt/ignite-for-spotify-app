import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";

const analytics = {
  loginCompleted: mock(() => undefined),
  loginInitiated: mock(() => undefined),
  logout: mock(() => undefined),
};

mock.module("../src/lib/analytics", () => ({ analytics }));

const { authStore } = await import("../src/stores/authStore");

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const replaceLocation = mock(() => undefined);

const session = {
  sessionId: "session-123",
  profile: {
    id: "spotify-user-123",
    displayName: "Test Listener",
    imageUrl: null,
  },
  expiresAt: "2030-01-01T00:00:00.000Z",
};

async function initializeAuthenticatedSession() {
  globalThis.fetch = mock(async () => Response.json(session)) as typeof fetch;
  await authStore.initAuth();
}

beforeEach(() => {
  replaceLocation.mockClear();
  analytics.logout.mockClear();
  analytics.logout.mockImplementation(() => undefined);
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { location: { replace: replaceLocation, search: "" } },
  });
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: originalWindow,
  });
});

describe("auth store OAuth callback", () => {
  test("shows a retry message when Spotify rejects an expired sign-in link", async () => {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: { location: { replace: replaceLocation, search: "?error=auth_expired" } },
    });
    globalThis.fetch = mock(
      async () => new Response(null, { status: 401 })
    ) as typeof fetch;

    await authStore.initAuth();

    expect(authStore.isAuthenticated()).toBe(false);
    expect(authStore.error()).toBe(
      "Your Spotify sign-in link expired. Please try again."
    );
  });
});

describe("auth store logout", () => {
  test("successful logout clears the session and replaces the current page with home", async () => {
    await initializeAuthenticatedSession();
    globalThis.fetch = mock(
      async () => new Response(null, { status: 200 })
    ) as typeof fetch;

    await authStore.logout();

    expect(authStore.isAuthenticated()).toBe(false);
    expect(analytics.logout).toHaveBeenCalledTimes(1);
    expect(replaceLocation).toHaveBeenCalledWith("/");
  });

  test("ignores duplicate logout attempts while one is pending", async () => {
    await initializeAuthenticatedSession();
    let resolveLogout!: (response: Response) => void;
    const logoutResponse = new Promise<Response>((resolve) => {
      resolveLogout = resolve;
    });
    const fetchMock = mock(async () => logoutResponse);
    globalThis.fetch = fetchMock as typeof fetch;

    const firstLogout = authStore.logout();
    const duplicateLogout = authStore.logout();

    expect(authStore.isLoggingOut()).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    resolveLogout(new Response(null, { status: 200 }));
    await Promise.all([firstLogout, duplicateLogout]);

    expect(authStore.isLoggingOut()).toBe(false);
  });

  test("failed logout preserves the session and exposes an error", async () => {
    await initializeAuthenticatedSession();
    globalThis.fetch = mock(
      async () =>
        Response.json(
          { message: "Session store unavailable" },
          { status: 503, statusText: "" }
        )
    ) as typeof fetch;

    await authStore.logout();

    expect(authStore.isAuthenticated()).toBe(true);
    expect(authStore.error()).toBe("Session store unavailable");
    expect(authStore.isLoggingOut()).toBe(false);
    expect(analytics.logout).not.toHaveBeenCalled();
    expect(replaceLocation).not.toHaveBeenCalled();
  });

  test("analytics failures do not interrupt a successful logout", async () => {
    await initializeAuthenticatedSession();
    globalThis.fetch = mock(
      async () => new Response(null, { status: 200 })
    ) as typeof fetch;
    analytics.logout.mockImplementation(() => {
      throw new Error("Analytics unavailable");
    });

    await authStore.logout();

    expect(authStore.isAuthenticated()).toBe(false);
    expect(authStore.error()).toBeNull();
    expect(replaceLocation).toHaveBeenCalledWith("/");
  });
});
