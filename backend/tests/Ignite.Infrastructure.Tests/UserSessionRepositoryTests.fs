module Ignite.Infrastructure.Tests.UserSessionRepositoryTests

open System
open System.Threading
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Data
open Ignite.Infrastructure.Data.Repositories
open Microsoft.Data.Sqlite
open Microsoft.EntityFrameworkCore
open Xunit

let private createContextAsync () =
    task {
        let connection = new SqliteConnection("Data Source=:memory:")
        do! connection.OpenAsync()

        let options =
            DbContextOptionsBuilder<IgniteDbContext>()
                .UseSqlite(connection)
                .Options

        let context = new IgniteDbContext(options)
        let! _ = context.Database.EnsureCreatedAsync()
        return connection, context
    }

[<Fact>]
let ``new session IDs are prefixed and round trip unchanged`` () =
    task {
        let! connection, context = createContextAsync ()
        use connection = connection
        use context = context
        let repository = UserSessionRepository(context) :> IUserSessionRepository
        let sessionId = UserSessionId.create ()
        let session = UserSession(Id = sessionId, SpotifyAccessToken = "token")

        let! _ = repository.CreateAsync(session, CancellationToken.None)
        context.ChangeTracker.Clear()
        let! loaded = repository.GetByIdAsync(sessionId, CancellationToken.None)

        Assert.StartsWith(UserSessionId.Prefix, sessionId)
        Assert.Equal(40, sessionId.Length)
        Assert.Equal(sessionId, loaded.Id)
        Assert.Equal("token", loaded.SpotifyAccessToken)
    }

[<Fact>]
let ``legacy hyphenated IDs resolve update and delete the canonical session`` () =
    task {
        let! connection, context = createContextAsync ()
        use connection = connection
        use context = context
        let repository = UserSessionRepository(context) :> IUserSessionRepository
        let canonicalId = Guid.NewGuid().ToString("N")
        let hyphenatedId = Guid.Parse(canonicalId).ToString("D")
        let session = UserSession(Id = canonicalId, SpotifyAccessToken = "old-token")

        let! _ = repository.CreateAsync(session, CancellationToken.None)
        context.ChangeTracker.Clear()

        let! loaded = repository.GetByIdAsync(hyphenatedId, CancellationToken.None)
        Assert.Equal(canonicalId, loaded.Id)

        loaded.SpotifyAccessToken <- "new-token"
        let! _ = repository.UpdateAsync(loaded, CancellationToken.None)
        context.ChangeTracker.Clear()

        let! updated = repository.GetByIdAsync(canonicalId, CancellationToken.None)
        Assert.Equal(canonicalId, updated.Id)
        Assert.Equal("new-token", updated.SpotifyAccessToken)

        do! repository.DeleteAsync(hyphenatedId, CancellationToken.None)
        context.ChangeTracker.Clear()
        let! remaining = context.UserSessions.CountAsync()
        Assert.Equal(0, remaining)
    }
