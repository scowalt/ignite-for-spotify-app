namespace Ignite.Infrastructure.Data

open System
open System.Linq
open Ignite.Core.Entities
open Microsoft.EntityFrameworkCore

type IgniteDbContext(options: DbContextOptions<IgniteDbContext>) =
    inherit DbContext(options)

    member _.Songs = base.Set<Song>()
    member _.UserSessions = base.Set<UserSession>()
    member _.ScrapingJobs = base.Set<ScrapingJob>()
    member _.PlaylistSearchSnapshots = base.Set<PlaylistSearchSnapshot>()

    override _.OnModelCreating(modelBuilder: ModelBuilder) =
        base.OnModelCreating(modelBuilder)

        modelBuilder.Entity<Song>(fun entity ->
            entity.ToTable("songs") |> ignore
            entity.HasKey(fun e -> e.Id :> obj) |> ignore
            entity.Property(fun e -> e.Id).HasColumnName("id") |> ignore
            entity.Property(fun e -> e.Artist).HasColumnName("artist").IsRequired() |> ignore
            entity.Property(fun e -> e.Title).HasColumnName("title").IsRequired() |> ignore
            entity.Property(fun e -> e.Album).HasColumnName("album").IsRequired() |> ignore
            entity.Property(fun e -> e.Tuning).HasColumnName("tuning") |> ignore
            entity.Property(fun e -> e.Version).HasColumnName("version") |> ignore
            entity.Property(fun e -> e.Author).HasColumnName("author") |> ignore
            entity.Property(fun e -> e.DateAddedToCdlc).HasColumnName("date_added_to_ignition") |> ignore
            entity.Property(fun e -> e.DateUpdatedInCdlc).HasColumnName("date_updated_in_ignition") |> ignore
            entity.Property(fun e -> e.Lead).HasColumnName("lead") |> ignore
            entity.Property(fun e -> e.Rhythm).HasColumnName("rhythm") |> ignore
            entity.Property(fun e -> e.Bass).HasColumnName("bass") |> ignore
            entity.Property(fun e -> e.Vocals).HasColumnName("vocals") |> ignore
            entity.Property(fun e -> e.DynamicDifficulty).HasColumnName("dynamic_difficulty") |> ignore
            entity.Property(fun e -> e.OfficialDlc).HasColumnName("official_dlc") |> ignore
            entity.Property(fun e -> e.DownloadLink).HasColumnName("download_link").IsRequired() |> ignore
            entity.Property(fun e -> e.SpotifyTrackId).HasColumnName("spotify_track_id") |> ignore
            entity.Property(fun e -> e.CreatedAt).HasColumnName("created_at") |> ignore
            entity.Property(fun e -> e.UpdatedAt).HasColumnName("updated_at") |> ignore

            entity
                .HasIndex("Artist", "Title", "Author", "Version")
                .IsUnique()
            |> ignore

            entity.HasIndex(fun e -> e.SpotifyTrackId :> obj) |> ignore
            entity.HasIndex(fun e -> e.Artist :> obj) |> ignore
            entity.HasIndex(fun e -> e.Title :> obj) |> ignore
            entity.HasIndex(fun e -> e.Album :> obj) |> ignore
            entity.HasIndex(fun e -> e.Author :> obj) |> ignore

            entity.HasIndex("Lead", "Rhythm", "Bass", "Vocals", "DynamicDifficulty")
            |> ignore)
        |> ignore

        modelBuilder.Entity<UserSession>(fun entity ->
            entity.ToTable("user_sessions") |> ignore
            entity.HasKey(fun e -> e.Id :> obj) |> ignore
            entity.Property(fun e -> e.Id).HasColumnName("id") |> ignore
            entity.Property(fun e -> e.SpotifyAccessToken).HasColumnName("spotify_access_token") |> ignore
            entity.Property(fun e -> e.SpotifyRefreshToken).HasColumnName("spotify_refresh_token") |> ignore
            entity.Property(fun e -> e.TokenExpiresAt).HasColumnName("token_expires_at") |> ignore
            entity.Property(fun e -> e.CreatedAt).HasColumnName("created_at") |> ignore
            entity.Property(fun e -> e.UpdatedAt).HasColumnName("updated_at") |> ignore
            entity.HasIndex(fun e -> e.TokenExpiresAt :> obj) |> ignore)
        |> ignore

        modelBuilder.Entity<ScrapingJob>(fun entity ->
            entity.ToTable("scraping_jobs") |> ignore
            entity.HasKey(fun e -> e.Id :> obj) |> ignore
            entity.Property(fun e -> e.Id).HasColumnName("id") |> ignore

            entity
                .Property(fun e -> e.JobType)
                .HasColumnName("job_type")
                .HasConversion<string>()
            |> ignore

            entity
                .Property(fun e -> e.Status)
                .HasColumnName("status")
                .HasConversion<string>()
            |> ignore

            entity.Property(fun e -> e.StartedAt).HasColumnName("started_at") |> ignore
            entity.Property(fun e -> e.CompletedAt).HasColumnName("completed_at") |> ignore
            entity.Property(fun e -> e.SongsProcessed).HasColumnName("songs_processed") |> ignore
            entity.Property(fun e -> e.SongsAdded).HasColumnName("songs_added") |> ignore
            entity.Property(fun e -> e.SongsUpdated).HasColumnName("songs_updated") |> ignore
            entity.Property(fun e -> e.ErrorMessage).HasColumnName("error_message") |> ignore
            entity.Property(fun e -> e.CreatedAt).HasColumnName("created_at") |> ignore)
        |> ignore

        modelBuilder.Entity<PlaylistSearchSnapshot>(fun entity ->
            entity.ToTable("playlist_search_snapshots") |> ignore
            entity.HasKey(fun e -> e.Id :> obj) |> ignore
            entity.Property(fun e -> e.Id).HasColumnName("id") |> ignore
            entity.Property(fun e -> e.SpotifyUserId).HasColumnName("spotify_user_id").IsRequired() |> ignore
            entity.Property(fun e -> e.PlaylistId).HasColumnName("playlist_id").IsRequired() |> ignore
            entity.Property(fun e -> e.ResultsJson).HasColumnName("results_json").IsRequired() |> ignore
            entity.Property(fun e -> e.TotalTracks).HasColumnName("total_tracks") |> ignore
            entity.Property(fun e -> e.ProcessedTracks).HasColumnName("processed_tracks") |> ignore
            entity.Property(fun e -> e.MatchedTracks).HasColumnName("matched_tracks") |> ignore
            entity.Property(fun e -> e.TotalMatches).HasColumnName("total_matches") |> ignore
            entity.Property(fun e -> e.SkippedTracks).HasColumnName("skipped_tracks") |> ignore
            entity.Property(fun e -> e.FailedTracks).HasColumnName("failed_tracks") |> ignore
            entity.Property(fun e -> e.UnprocessedTracks).HasColumnName("unprocessed_tracks") |> ignore
            entity.Property(fun e -> e.DurationTicks).HasColumnName("duration_ticks") |> ignore
            entity.Property(fun e -> e.GeneratedAt).HasColumnName("generated_at") |> ignore
            entity.Property(fun e -> e.CreatedAt).HasColumnName("created_at") |> ignore
            entity.Property(fun e -> e.UpdatedAt).HasColumnName("updated_at") |> ignore

            entity
                .HasIndex("SpotifyUserId", "PlaylistId")
                .HasDatabaseName("ix_playlist_search_snapshots_user_playlist")
                .IsUnique()
            |> ignore)
        |> ignore

    override this.SaveChanges() =
        this.UpdateTimestamps()
        base.SaveChanges()

    override this.SaveChangesAsync(cancellationToken) =
        this.UpdateTimestamps()
        base.SaveChangesAsync(cancellationToken)

    member private this.UpdateTimestamps() =
        let entries =
            this.ChangeTracker.Entries() |> Seq.filter (fun e -> e.State = EntityState.Modified)

        for entry in entries do
            match entry.Entity with
            | :? Song as song -> song.UpdatedAt <- DateTime.UtcNow
            | :? UserSession as session -> session.UpdatedAt <- DateTime.UtcNow
            | :? PlaylistSearchSnapshot as snapshot -> snapshot.UpdatedAt <- DateTime.UtcNow
            | _ -> ()
