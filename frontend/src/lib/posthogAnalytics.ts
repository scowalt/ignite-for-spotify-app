import type {
  CaptureResult,
  CapturedNetworkRequest,
  PostHogConfig,
} from "posthog-js";
import type { SpotifyUserProfile } from "../types/api";

type AnalyticsProperties = Record<string, unknown>;
type AnalyticsWarning = (message: string, error?: unknown) => void;

export interface PostHogAnalyticsClient {
  init(apiKey: string, config: Partial<PostHogConfig>): unknown;
  capture(eventName: string, properties?: AnalyticsProperties): unknown;
  identify(distinctId: string, properties?: AnalyticsProperties): unknown;
  reset(): unknown;
}

const DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com";
const CAPTURED_URL_PROPERTIES = [
  "$current_url",
  "$referrer",
  "$initial_current_url",
  "$initial_referrer",
  "$session_entry_url",
  "$session_entry_referrer",
  "$external_click_url",
  "$url",
  "current_url",
  "request_url",
  "href",
  "url",
] as const;

function stripUrlDetails(url: string): string {
  return url.replace(/[?#].*$/, "");
}

function sanitizeUrlProperties(
  properties: AnalyticsProperties,
): AnalyticsProperties {
  const sanitized = { ...properties };

  for (const property of CAPTURED_URL_PROPERTIES) {
    const value = sanitized[property];
    if (typeof value === "string") {
      sanitized[property] = stripUrlDetails(value);
    }
  }

  if (Array.isArray(sanitized.$elements)) {
    sanitized.$elements = sanitized.$elements.map((element: unknown) => {
      if (
        typeof element !== "object" ||
        element === null ||
        !("attr__href" in element) ||
        typeof element.attr__href !== "string"
      ) {
        return element;
      }

      return {
        ...element,
        attr__href: stripUrlDetails(element.attr__href),
      };
    });
  }

  const snapshotData = sanitized.$snapshot_data;
  if (
    typeof snapshotData === "object" &&
    snapshotData !== null &&
    "href" in snapshotData &&
    typeof snapshotData.href === "string"
  ) {
    sanitized.$snapshot_data = {
      ...snapshotData,
      href: stripUrlDetails(snapshotData.href),
    };
  }

  return sanitized;
}

export function sanitizePostHogEvent(
  captureResult: CaptureResult | null,
): CaptureResult | null {
  if (!captureResult) {
    return null;
  }

  return {
    ...captureResult,
    properties: sanitizeUrlProperties(captureResult.properties),
    ...(captureResult.$set && {
      $set: sanitizeUrlProperties(captureResult.$set),
    }),
    ...(captureResult.$set_once && {
      $set_once: sanitizeUrlProperties(captureResult.$set_once),
    }),
  };
}

export function sanitizeReplayRequest(
  request: CapturedNetworkRequest,
): CapturedNetworkRequest {
  return {
    ...request,
    name: stripUrlDetails(request.name),
    requestHeaders: undefined,
    requestBody: undefined,
    responseHeaders: undefined,
    responseBody: undefined,
  };
}

export function createPostHogConfig(
  apiHost: string | undefined,
  isProduction: boolean,
): Partial<PostHogConfig> {
  return {
    api_host: apiHost || DEFAULT_POSTHOG_HOST,
    capture_pageview: true,
    capture_pageleave: true,
    disable_session_recording: !isProduction,
    enable_recording_console_log: false,
    disable_capture_url_hashes: true,
    before_send: sanitizePostHogEvent,
    capture_performance: {
      network_timing: true,
    },
    session_recording: {
      maskAllInputs: true,
      recordHeaders: false,
      recordBody: false,
      strictMinimumDuration: true,
      maskCapturedNetworkRequestFn: sanitizeReplayRequest,
    },
  };
}

export class PostHogAnalyticsRuntime {
  private initialized = false;
  private pendingProfile: SpotifyUserProfile | undefined;
  private completedLoginId: string | undefined;

  constructor(
    private readonly client: PostHogAnalyticsClient,
    private readonly warn: AnalyticsWarning = (message, error) => {
      if (error === undefined) {
        console.warn(message);
        return;
      }

      console.warn(message, error);
    },
  ) {}

  init(
    apiKey: string | undefined,
    apiHost: string | undefined,
    isProduction: boolean,
  ): void {
    if (this.initialized) {
      return;
    }

    if (!apiKey) {
      this.warn("PostHog API key not configured");
      return;
    }

    try {
      this.client.init(apiKey, createPostHogConfig(apiHost, isProduction));
      this.initialized = true;
    } catch (error) {
      this.warn("PostHog initialization failed", error);
      return;
    }

    if (this.pendingProfile) {
      const profile = this.pendingProfile;
      this.pendingProfile = undefined;
      this.completeLogin(profile);
    }
  }

  capture(eventName: string, properties?: AnalyticsProperties): void {
    this.runSafely(`capture ${eventName}`, () => {
      this.client.capture(eventName, properties);
    });
  }

  loginCompleted(profile: SpotifyUserProfile): void {
    if (this.completedLoginId === profile.id) {
      return;
    }

    if (!this.initialized) {
      this.pendingProfile = profile;
      return;
    }

    this.completeLogin(profile);
  }

  logout(): void {
    this.pendingProfile = undefined;
    this.completedLoginId = undefined;
    this.capture("logout");
    this.runSafely("reset", () => {
      this.client.reset();
    });
  }

  private completeLogin(profile: SpotifyUserProfile): void {
    if (this.completedLoginId === profile.id) {
      return;
    }

    this.completedLoginId = profile.id;
    this.runSafely("identify", () => {
      this.client.identify(profile.id, {
        name: profile.displayName,
        $avatar: profile.imageUrl,
      });
    });
    this.capture("login_completed", { userId: profile.id });
  }

  private runSafely(operation: string, action: () => void): void {
    try {
      action();
    } catch (error) {
      this.warn(`PostHog ${operation} failed`, error);
    }
  }
}
