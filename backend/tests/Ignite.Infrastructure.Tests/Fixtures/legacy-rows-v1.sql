INSERT INTO songs (id, artist, title, album, lead, rhythm, bass, vocals, dynamic_difficulty, download_link, created_at, updated_at)
VALUES (1, 'Legacy Artist', 'Signal Fire', 'Test Album', 0, 0, 0, 0, 0, 'https://example.test/song', '2000-01-01', '2000-01-01');
INSERT INTO user_sessions (id, SpotifyUserId, spotify_access_token, spotify_refresh_token, created_at, updated_at)
VALUES ('session_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'fixture-user', 'fixture-access', 'fixture-refresh', '2000-01-01', '2000-01-01');
INSERT INTO scraping_jobs (id, job_type, status, HangfireJobId, songs_processed, songs_added, songs_updated, created_at)
VALUES (1, 'CdlcIncremental', 'Completed', 'fixture-job', 0, 0, 0, '2000-01-01');
INSERT INTO playlist_search_snapshots (id, spotify_user_id, playlist_id, results_json, total_tracks, processed_tracks, matched_tracks, total_matches, skipped_tracks, failed_tracks, unprocessed_tracks, duration_ticks, generated_at, created_at, updated_at)
VALUES (1, 'fixture-user', 'fixture-playlist', '[]', 12, 12, 0, 0, 0, 0, 0, 0, '2000-01-01', '2000-01-01', '2000-01-01');
