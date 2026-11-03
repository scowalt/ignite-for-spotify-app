CREATE TABLE "scraping_jobs" (
    "id" INTEGER NOT NULL CONSTRAINT "PK_scraping_jobs" PRIMARY KEY AUTOINCREMENT,
    "job_type" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "HangfireJobId" TEXT NULL,
    "started_at" TEXT NULL,
    "completed_at" TEXT NULL,
    "songs_processed" INTEGER NOT NULL,
    "songs_added" INTEGER NOT NULL,
    "songs_updated" INTEGER NOT NULL,
    "error_message" TEXT NULL,
    "created_at" TEXT NOT NULL
);
CREATE TABLE "songs" (
    "id" INTEGER NOT NULL CONSTRAINT "PK_songs" PRIMARY KEY AUTOINCREMENT,
    "artist" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "album" TEXT NOT NULL,
    "tuning" TEXT NULL,
    "version" TEXT NULL,
    "author" TEXT NULL,
    "date_added_to_ignition" TEXT NULL,
    "date_updated_in_ignition" TEXT NULL,
    "lead" INTEGER NOT NULL,
    "rhythm" INTEGER NOT NULL,
    "bass" INTEGER NOT NULL,
    "vocals" INTEGER NOT NULL,
    "dynamic_difficulty" INTEGER NOT NULL,
    "download_link" TEXT NOT NULL,
    "spotify_track_id" TEXT NULL,
    "created_at" TEXT NOT NULL,
    "updated_at" TEXT NOT NULL
);
CREATE TABLE "user_sessions" (
    "id" TEXT NOT NULL CONSTRAINT "PK_user_sessions" PRIMARY KEY,
    "SpotifyUserId" TEXT NULL,
    "spotify_access_token" TEXT NULL,
    "spotify_refresh_token" TEXT NULL,
    "token_expires_at" TEXT NULL,
    "created_at" TEXT NOT NULL,
    "updated_at" TEXT NOT NULL
);
CREATE INDEX "IX_songs_album" ON "songs" ("album");
CREATE INDEX "IX_songs_artist" ON "songs" ("artist");
CREATE UNIQUE INDEX "IX_songs_artist_title_author_version" ON "songs" ("artist", "title", "author", "version");
CREATE INDEX "IX_songs_author" ON "songs" ("author");
CREATE INDEX "IX_songs_lead_rhythm_bass_vocals_dynamic_difficulty" ON "songs" ("lead", "rhythm", "bass", "vocals", "dynamic_difficulty");
CREATE INDEX "IX_songs_spotify_track_id" ON "songs" ("spotify_track_id");
CREATE INDEX "IX_songs_title" ON "songs" ("title");
CREATE INDEX "IX_user_sessions_token_expires_at" ON "user_sessions" ("token_expires_at");
CREATE VIRTUAL TABLE songs_fts USING fts5(
  artist,
  title,
  album,
  content='songs',
  content_rowid='id'
);
CREATE TRIGGER songs_ai AFTER INSERT ON songs BEGIN
  INSERT INTO songs_fts(rowid, artist, title, album)
    VALUES (new.id, new.artist, new.title, new.album);
END;
CREATE TRIGGER songs_ad AFTER DELETE ON songs BEGIN
  INSERT INTO songs_fts(songs_fts, rowid, artist, title, album)
    VALUES ('delete', old.id, old.artist, old.title, old.album);
END;
CREATE TRIGGER songs_au AFTER UPDATE ON songs BEGIN
  INSERT INTO songs_fts(songs_fts, rowid, artist, title, album)
    VALUES ('delete', old.id, old.artist, old.title, old.album);
  INSERT INTO songs_fts(rowid, artist, title, album)
    VALUES (new.id, new.artist, new.title, new.album);
END;
ALTER TABLE songs ADD COLUMN official_dlc INTEGER NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS playlist_search_snapshots (
                        id INTEGER NOT NULL CONSTRAINT pk_playlist_search_snapshots PRIMARY KEY AUTOINCREMENT,
                        spotify_user_id TEXT NOT NULL,
                        playlist_id TEXT NOT NULL,
                        results_json TEXT NOT NULL,
                        total_tracks INTEGER NOT NULL,
                        processed_tracks INTEGER NOT NULL,
                        matched_tracks INTEGER NOT NULL,
                        total_matches INTEGER NOT NULL,
                        skipped_tracks INTEGER NOT NULL,
                        failed_tracks INTEGER NOT NULL,
                        unprocessed_tracks INTEGER NOT NULL,
                        duration_ticks INTEGER NOT NULL,
                        generated_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
CREATE UNIQUE INDEX IF NOT EXISTS ix_playlist_search_snapshots_user_playlist
                    ON playlist_search_snapshots (spotify_user_id, playlist_id)
                    ;
