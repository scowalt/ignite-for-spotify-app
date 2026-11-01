import * as signalR from "@microsoft/signalr";

const HUB_URL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL.replace("/api", "")}/hubs/search`
  : "/hubs/search";

export interface SearchProgressUpdate {
  sessionId: string;
  processed: number;
  total: number;
  currentItem: string;
}

export interface SpotifyTrackInfo {
  id: string;
  name: string;
  artists: string[];
  album: string;
}

export interface CdlcMatchInfo {
  id: number;
  artist: string;
  title: string;
  album: string;
  author: string | null;
  lead: boolean;
  rhythm: boolean;
  bass: boolean;
  vocals: boolean;
  officialDlc: boolean;
  downloadLink: string;
}

export interface SearchResultUpdate {
  sessionId: string;
  spotifyTrack: SpotifyTrackInfo;
  matches: CdlcMatchInfo[];
  matchCount: number;
}

export interface SearchCompleteUpdate {
  sessionId: string;
  totalTracks: number;
  processedTracks: number;
  matchedTracks: number;
  totalMatches: number;
  skippedTracks: number;
  failedTracks: number;
  unprocessedTracks: number;
  isComplete: boolean;
  failureReason: string | null;
  duration: string;  
}

export interface JobProgressUpdate {
  jobId: string;
  jobType: string;
  processed: number;
  total: number;
  added: number;
  updated: number;
  status: string;
}

export interface JobCompleteUpdate {
  jobId: string;
  jobType: string;
  status: string;
  totalProcessed: number;
  added: number;
  updated: number;
  errorMessage: string | null;
  duration: string;
}

export interface ErrorUpdate {
  sessionId: string;
  message: string;
  details: string | null;
}

type SearchHubEvents = {
  ReceiveSearchProgress: (update: SearchProgressUpdate) => void;
  ReceiveSearchResult: (update: SearchResultUpdate) => void;
  ReceiveSearchComplete: (update: SearchCompleteUpdate) => void;
  ReceiveJobProgress: (update: JobProgressUpdate) => void;
  ReceiveJobComplete: (update: JobCompleteUpdate) => void;
  ReceiveError: (update: ErrorUpdate) => void;
};

class SearchHubConnection {
  private connection: signalR.HubConnection | null = null;
  private maxReconnectAttempts = 5;

  async start(): Promise<void> {
    if (this.connection?.state === signalR.HubConnectionState.Connected) {
      return;
    }

    this.connection = new signalR.HubConnectionBuilder()
      .withUrl(HUB_URL)
      .withAutomaticReconnect({
        nextRetryDelayInMilliseconds: (retryContext) => {
          if (retryContext.previousRetryCount >= this.maxReconnectAttempts) {
            return null;  
          }
          return Math.min(
            1000 * Math.pow(2, retryContext.previousRetryCount),
            30000
          );
        },
      })
      .configureLogging(signalR.LogLevel.Information)
      .build();

    try {
      await this.connection.start();
      console.log("SignalR connected");
    } catch (err) {
      console.error("SignalR connection failed:", err);
      throw err;
    }
  }

  async stop(): Promise<void> {
    if (this.connection) {
      await this.connection.stop();
      this.connection = null;
    }
  }

  on<K extends keyof SearchHubEvents>(
    event: K,
    callback: SearchHubEvents[K]
  ): void {
    this.connection?.on(event, callback);
  }

  off<K extends keyof SearchHubEvents>(event: K): void {
    this.connection?.off(event);
  }

  async joinSearchSession(sessionId: string): Promise<void> {
    await this.connection?.invoke("JoinSearchSession", sessionId);
  }

  async leaveSearchSession(sessionId: string): Promise<void> {
    await this.connection?.invoke("LeaveSearchSession", sessionId);
  }

  async joinJobUpdates(jobId: string): Promise<void> {
    await this.connection?.invoke("JoinJobUpdates", jobId);
  }

  async leaveJobUpdates(jobId: string): Promise<void> {
    await this.connection?.invoke("LeaveJobUpdates", jobId);
  }

  get state(): signalR.HubConnectionState {
    return this.connection?.state ?? signalR.HubConnectionState.Disconnected;
  }

  get isConnected(): boolean {
    return this.connection?.state === signalR.HubConnectionState.Connected;
  }
}

export const searchHub = new SearchHubConnection();
