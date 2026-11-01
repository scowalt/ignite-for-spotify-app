import { afterEach, describe, expect, mock, test } from "bun:test";
import { auth } from "../src/lib/api";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("auth API", () => {
  test("logout accepts a successful response with an empty body", async () => {
    const fetchMock = mock(async () =>
      new Response(null, { status: 200, statusText: "OK" })
    );
    globalThis.fetch = fetchMock as typeof fetch;

    await expect(auth.logout()).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
    });
  });

  test("logout accepts a 204 No Content response", async () => {
    globalThis.fetch = mock(
      async () => new Response(null, { status: 204 })
    ) as typeof fetch;

    await expect(auth.logout()).resolves.toBeUndefined();
  });

  test("session requests still parse successful JSON responses", async () => {
    const session = {
      sessionId: "session-123",
      profile: {
        id: "spotify-user-123",
        displayName: "Test Listener",
        imageUrl: null,
      },
      expiresAt: "2030-01-01T00:00:00.000Z",
    };
    globalThis.fetch = mock(
      async () => Response.json(session)
    ) as typeof fetch;

    await expect(auth.getSession()).resolves.toEqual(session);
  });

  test("failed logout responses still reject with API details", async () => {
    globalThis.fetch = mock(
      async () =>
        Response.json(
          { message: "Session store unavailable" },
          { status: 503, statusText: "Service Unavailable" }
        )
    ) as typeof fetch;

    await expect(auth.logout()).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      message: "Service Unavailable",
      details: { message: "Session store unavailable" },
    });
  });

  test("failed responses have a visible message when status text is empty", async () => {
    globalThis.fetch = mock(
      async () =>
        Response.json(
          { message: "Session store unavailable" },
          { status: 503, statusText: "" }
        )
    ) as typeof fetch;

    await expect(auth.logout()).rejects.toMatchObject({
      message: "Session store unavailable",
    });
  });

  test("failed empty responses fall back to their HTTP status", async () => {
    globalThis.fetch = mock(
      async () => new Response(null, { status: 503, statusText: "" })
    ) as typeof fetch;

    await expect(auth.logout()).rejects.toMatchObject({
      message: "Request failed with status 503",
    });
  });
});
