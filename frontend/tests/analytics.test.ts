import { describe, expect, mock, test } from "bun:test";
import type { CaptureResult, CapturedNetworkRequest } from "posthog-js";
import type { SpotifyUserProfile } from "../src/types/api";
import {
  createPostHogConfig,
  PostHogAnalyticsRuntime,
  sanitizePostHogEvent,
  sanitizeReplayRequest,
  type PostHogAnalyticsClient,
} from "../src/lib/posthogAnalytics";

const profile: SpotifyUserProfile = {
  id: "spotify-user-123",
  displayName: "Test Listener",
  imageUrl: "https://images.example.test/listener.jpg",
};

function createMockClient() {
  const init = mock(() => undefined);
  const capture = mock(() => undefined);
  const identify = mock(() => undefined);
  const reset = mock(() => undefined);

  const client = {
    init,
    capture,
    identify,
    reset,
  } satisfies PostHogAnalyticsClient;

  return { client, init, capture, identify, reset };
}

function createReplayRequest(): CapturedNetworkRequest {
  return {
    name: "https://igniteforspotify.com/api/playlists?access_token=secret#selected",
    entryType: "resource",
    startTime: 12,
    duration: 34,
    initiatorType: "fetch",
    method: "GET",
    status: 200,
    requestHeaders: { authorization: "Bearer secret" },
    requestBody: "request secret",
    responseHeaders: { "x-private": "secret" },
    responseBody: "response secret",
  };
}

describe("PostHog session replay configuration", () => {
  test("enables hardened replay capture in production", () => {
    const config = createPostHogConfig(
      "https://analytics.example.test",
      true,
    );

    expect(config).toMatchObject({
      api_host: "https://analytics.example.test",
      capture_pageview: true,
      capture_pageleave: true,
      disable_session_recording: false,
      enable_recording_console_log: false,
      disable_capture_url_hashes: true,
      capture_performance: { network_timing: true },
      session_recording: {
        maskAllInputs: true,
        recordHeaders: false,
        recordBody: false,
        strictMinimumDuration: true,
      },
    });
    expect(config.session_recording?.maskTextSelector).toBeUndefined();
    expect(config.session_recording?.blockSelector).toBeUndefined();
  });

  test("disables replay outside production and falls back to the US host", () => {
    const config = createPostHogConfig(undefined, false);

    expect(config.api_host).toBe("https://us.i.posthog.com");
    expect(config.disable_session_recording).toBe(true);
  });

  test("sanitizes replay URLs and removes network payload fields", () => {
    const request = createReplayRequest();
    const sanitized = sanitizeReplayRequest(request);

    expect(sanitized).toEqual({
      ...request,
      name: "https://igniteforspotify.com/api/playlists",
      requestHeaders: undefined,
      requestBody: undefined,
      responseHeaders: undefined,
      responseBody: undefined,
    });
    expect(sanitized).not.toBe(request);
    expect(sanitized.method).toBe("GET");
    expect(sanitized.status).toBe(200);
    expect(sanitized.startTime).toBe(12);
    expect(sanitized.duration).toBe(34);
  });

  test("installs the replay sanitizer in the PostHog configuration", () => {
    const config = createPostHogConfig(undefined, true);
    const sanitizer = config.session_recording?.maskCapturedNetworkRequestFn;

    expect(sanitizer).toBe(sanitizeReplayRequest);
    expect(sanitizer?.(createReplayRequest())).toMatchObject({
      name: "https://igniteforspotify.com/api/playlists",
      method: "GET",
      status: 200,
      requestHeaders: undefined,
      requestBody: undefined,
      responseHeaders: undefined,
      responseBody: undefined,
    });
  });

  test("removes query strings and fragments from associated event URLs", () => {
    const event: CaptureResult = {
      uuid: "event-123",
      event: "$pageview",
      properties: {
        $current_url: "https://igniteforspotify.com/match?code=secret#results",
        $referrer: "https://accounts.spotify.com/authorize?token=secret",
        $session_entry_url: "https://igniteforspotify.com/discover?filter=private",
        ordinaryText: "Rendered text remains visible",
        $elements: [
          {
            tag_name: "a",
            attr__href: "/discover?filter=private#results",
          },
        ],
        $snapshot_data: {
          href: "https://igniteforspotify.com/match?code=secret#results",
          source: 0,
        },
      },
      $set_once: {
        $initial_current_url: "https://igniteforspotify.com/?code=secret",
      },
    };

    expect(sanitizePostHogEvent(event)).toEqual({
      ...event,
      properties: {
        ...event.properties,
        $current_url: "https://igniteforspotify.com/match",
        $referrer: "https://accounts.spotify.com/authorize",
        $session_entry_url: "https://igniteforspotify.com/discover",
        $elements: [
          {
            tag_name: "a",
            attr__href: "/discover",
          },
        ],
        $snapshot_data: {
          href: "https://igniteforspotify.com/match",
          source: 0,
        },
      },
      $set_once: {
        $initial_current_url: "https://igniteforspotify.com/",
      },
    });
    expect(sanitizePostHogEvent(null)).toBeNull();
    expect(createPostHogConfig(undefined, true).before_send).toBe(
      sanitizePostHogEvent,
    );
  });
});

describe("PostHog analytics runtime", () => {
  test("warns and remains retryable when the API key is missing", () => {
    const { client, init } = createMockClient();
    const warn = mock(() => undefined);
    const runtime = new PostHogAnalyticsRuntime(client, warn);

    runtime.init(undefined, undefined, true);

    expect(init).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledWith("PostHog API key not configured");

    runtime.init("phc_test", undefined, true);

    expect(init).toHaveBeenCalledTimes(1);
    expect(init).toHaveBeenCalledWith(
      "phc_test",
      createPostHogConfig(undefined, true),
    );
  });

  test("queues auth before initialization and completes it exactly once", () => {
    const { client, init, identify, capture } = createMockClient();
    const runtime = new PostHogAnalyticsRuntime(client);

    runtime.loginCompleted(profile);
    runtime.loginCompleted(profile);

    expect(identify).not.toHaveBeenCalled();
    expect(capture).not.toHaveBeenCalled();

    runtime.init("phc_test", "https://analytics.example.test", true);
    runtime.init("phc_test", "https://ignored.example.test", true);
    runtime.loginCompleted(profile);

    expect(init).toHaveBeenCalledTimes(1);
    expect(identify).toHaveBeenCalledTimes(1);
    expect(identify).toHaveBeenCalledWith(profile.id, {
      name: profile.displayName,
      $avatar: profile.imageUrl,
    });
    expect(capture).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledWith("login_completed", {
      userId: profile.id,
    });
  });

  test("completes auth after initialization exactly once", () => {
    const { client, identify, capture } = createMockClient();
    const runtime = new PostHogAnalyticsRuntime(client);

    runtime.init("phc_test", undefined, true);
    runtime.loginCompleted(profile);
    runtime.loginCompleted(profile);

    expect(identify).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledWith("login_completed", {
      userId: profile.id,
    });
  });

  test("contains initialization failures and flushes queued auth after retry", () => {
    const { client, init, identify, capture } = createMockClient();
    const warn = mock(() => undefined);
    const runtime = new PostHogAnalyticsRuntime(client, warn);
    const failure = new Error("SDK unavailable");
    init.mockImplementationOnce(() => {
      throw failure;
    });
    runtime.loginCompleted(profile);

    expect(() => runtime.init("phc_test", undefined, true)).not.toThrow();
    expect(warn).toHaveBeenCalledWith(
      "PostHog initialization failed",
      failure,
    );
    expect(identify).not.toHaveBeenCalled();
    expect(capture).not.toHaveBeenCalled();

    runtime.init("phc_test", undefined, true);

    expect(init).toHaveBeenCalledTimes(2);
    expect(identify).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledWith("login_completed", {
      userId: profile.id,
    });
  });

  test("contains identify failures and still attempts the login event", () => {
    const { client, identify, capture } = createMockClient();
    const warn = mock(() => undefined);
    const runtime = new PostHogAnalyticsRuntime(client, warn);
    const failure = new Error("identify failed");
    identify.mockImplementation(() => {
      throw failure;
    });
    runtime.init("phc_test", undefined, true);

    expect(() => runtime.loginCompleted(profile)).not.toThrow();
    expect(warn).toHaveBeenCalledWith("PostHog identify failed", failure);
    expect(capture).toHaveBeenCalledWith("login_completed", {
      userId: profile.id,
    });
  });

  test("captures logout, resets identity, and permits a later login", () => {
    const { client, identify, capture, reset } = createMockClient();
    const runtime = new PostHogAnalyticsRuntime(client);
    runtime.init("phc_test", undefined, true);
    runtime.loginCompleted(profile);
    capture.mockClear();
    identify.mockClear();

    runtime.logout();

    expect(capture).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledWith("logout", undefined);
    expect(reset).toHaveBeenCalledTimes(1);

    runtime.loginCompleted(profile);

    expect(identify).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledWith("login_completed", {
      userId: profile.id,
    });
  });

  test("contains capture and reset failures during logout", () => {
    const { client, capture, reset } = createMockClient();
    const warn = mock(() => undefined);
    const runtime = new PostHogAnalyticsRuntime(client, warn);
    const captureFailure = new Error("capture failed");
    const resetFailure = new Error("reset failed");
    capture.mockImplementation(() => {
      throw captureFailure;
    });
    reset.mockImplementation(() => {
      throw resetFailure;
    });

    expect(() => runtime.logout()).not.toThrow();
    expect(capture).toHaveBeenCalledWith("logout", undefined);
    expect(reset).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledWith(
      "PostHog capture logout failed",
      captureFailure,
    );
    expect(warn).toHaveBeenCalledWith("PostHog reset failed", resetFailure);
  });

  test("logout before initialization clears a queued profile", () => {
    const { client, capture, identify, reset } = createMockClient();
    const runtime = new PostHogAnalyticsRuntime(client);
    runtime.loginCompleted(profile);

    runtime.logout();
    capture.mockClear();
    reset.mockClear();
    runtime.init("phc_test", undefined, true);

    expect(identify).not.toHaveBeenCalled();
    expect(capture).not.toHaveBeenCalled();
    expect(reset).not.toHaveBeenCalled();
  });
});
