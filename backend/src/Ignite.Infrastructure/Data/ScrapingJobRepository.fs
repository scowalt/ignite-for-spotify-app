namespace Ignite.Infrastructure.Data.Repositories

open System
open System.Linq
open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Ignite.Infrastructure.Data
open Microsoft.EntityFrameworkCore

type ScrapingJobRepository(context: IgniteDbContext) =
    interface IScrapingJobRepository with
        member _.GetByIdAsync(id: int, cancellationToken: CancellationToken) =
            task { return! context.ScrapingJobs.FindAsync([| id :> obj |], cancellationToken).AsTask() }

        member _.GetLatestAsync(jobType: Nullable<ScrapingJobType>, cancellationToken: CancellationToken) =
            task {
                let query =
                    if jobType.HasValue then
                        let jt = jobType.Value
                        context.ScrapingJobs.Where(fun j -> j.JobType = jt)
                    else
                        context.ScrapingJobs.AsQueryable()

                return! query.OrderByDescending(fun j -> j.CreatedAt).FirstOrDefaultAsync(cancellationToken)
            }

        member _.CreateAsync(job: ScrapingJob, cancellationToken: CancellationToken) =
            task {
                context.ScrapingJobs.Add(job) |> ignore
                do! context.SaveChangesAsync(cancellationToken) :> Task
                return job
            }

        member _.UpdateAsync(job: ScrapingJob, cancellationToken: CancellationToken) =
            task {
                context.ScrapingJobs.Update(job) |> ignore
                do! context.SaveChangesAsync(cancellationToken) :> Task
                return job
            }
