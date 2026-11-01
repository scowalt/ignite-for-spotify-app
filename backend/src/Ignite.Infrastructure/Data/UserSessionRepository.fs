namespace Ignite.Infrastructure.Data.Repositories

open System
open System.Linq
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Data
open Microsoft.EntityFrameworkCore

type UserSessionRepository(context: IgniteDbContext) =
    let canonicalizeSession (session: UserSession) =
        session.Id <- UserSessionId.canonicalize session.Id
        session

    let getByIdAsync (id: string) (cancellationToken: CancellationToken) =
        task {
            let canonicalId = UserSessionId.canonicalize id

            let! session =
                context.UserSessions
                    .AsNoTracking()
                    .Where(fun candidate -> candidate.Id = canonicalId)
                    .SingleOrDefaultAsync(cancellationToken)

            if not (isNull session) then
                session.Id <- canonicalId

            return session
        }

    interface IUserSessionRepository with
        member _.GetByIdAsync(id: string, cancellationToken: CancellationToken) =
            getByIdAsync id cancellationToken

        member _.CreateAsync(session: UserSession, cancellationToken: CancellationToken) =
            task {
                canonicalizeSession session |> ignore
                context.UserSessions.Add(session) |> ignore
                do! context.SaveChangesAsync(cancellationToken) :> Task
                return session
            }

        member _.UpdateAsync(session: UserSession, cancellationToken: CancellationToken) =
            task {
                canonicalizeSession session |> ignore
                context.UserSessions.Update(session) |> ignore
                do! context.SaveChangesAsync(cancellationToken) :> Task
                return session
            }

        member _.DeleteAsync(id: string, cancellationToken: CancellationToken) =
            task {
                let! session = getByIdAsync id cancellationToken

                if not (isNull session) then
                    context.UserSessions.Remove(session) |> ignore
                    do! context.SaveChangesAsync(cancellationToken) :> Task
            }
            :> Task

        member _.DeleteExpiredAsync(cancellationToken: CancellationToken) =
            task {
                let now = DateTime.UtcNow

                let! expired =
                    context.UserSessions
                        .AsNoTracking()
                        .Where(fun s -> s.TokenExpiresAt.HasValue && s.TokenExpiresAt.Value < now)
                        .ToListAsync(cancellationToken)

                if expired.Count > 0 then
                    for session in expired do
                        canonicalizeSession session |> ignore

                    context.UserSessions.RemoveRange(expired)
                    do! context.SaveChangesAsync(cancellationToken) :> Task
            }
            :> Task
