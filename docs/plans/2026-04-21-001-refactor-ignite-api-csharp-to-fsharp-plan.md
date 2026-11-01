---
title: "refactor: Migrate Ignite.Api from C# to F#"
type: refactor
status: active
date: 2026-04-21
---

# Migrate Ignite.Api from C# to F#

## Overview

Final phase of the C#→F# backend migration. Ignite.Api is the last production C# project (1,034 lines across 3 files). After this, the entire backend is F#.

Additionally, the sole test project (Ignite.Core.Tests, 1 trivial test file) will be converted to keep the solution fully F#.

## Scope

### In scope
- Convert `Program.cs` → `Program.fs` (ASP.NET minimal API entry point, 831 lines)
- Convert `Hubs/SearchHub.cs` → `Hubs/SearchHub.fs` (SignalR hub + DTOs, 133 lines)
- Convert `Hubs/HubNotificationService.cs` → `Hubs/HubNotificationService.fs` (70 lines)
- Convert `Ignite.Api.csproj` → `Ignite.Api.fsproj`
- Update solution files (`Ignite.sln`, `Ignite.slnx`) with F# project GUID
- Delete old C# files
- Convert `Ignite.Core.Tests` from C#/xUnit to F#/xUnit

### Out of scope
- Changing any API behavior, endpoints, or responses
- Refactoring endpoint structure (e.g., extracting modules)
- Changing any package versions

## Technical Considerations

### F# ASP.NET Minimal API
- F# doesn't have C#'s top-level statements. Use a `[<EntryPoint>] let main` or a module-level main function.
- `WebApplication.CreateBuilder(args)` works the same in F#.
- Minimal API `MapGet`/`MapPost` lambdas: F# lambdas work but need explicit `Func<>` wrapping or `RequestDelegate` for complex signatures with DI-injected parameters. The simplest approach is using `Func<..., Task<IResult>>` delegates.
- C# anonymous objects (`new { ... }`) → F# anonymous records (`{| ... |}`).
- C# `var (total, withSpotify) = await ...` → F# `let! struct (total, withSpotify) = ...`.
- C# `string.IsNullOrEmpty(x)` → F# `String.IsNullOrEmpty(x)`.
- C# `try { } catch { }` → F# `try ... with _ -> ...`.
- C# `Results.Ok(...)`, `Results.Redirect(...)` etc. work identically via `Microsoft.AspNetCore.Http.Results`.

### SignalR Hub in F#
- `Hub<T>` inheritance works in F#: `type SearchHub(logger) = inherit Hub<ISearchHubClient>()`.
- Interface definitions: use `[<AllowNullLiteral>]` where needed for nullable parameters.
- C# records → F# CLR records with `[<CLIMutable>]` for serialization, or keep as classes. Since these are DTOs serialized by SignalR/JSON, simple F# types with constructors work.

### Request DTOs
- C# `record` types used for request bodies (`SearchFromPlaylistRequest`, `ExportToPlaylistRequest`, `CdlcSearchRequest`) need to be deserializable from JSON. Use `[<CLIMutable>]` F# records or classes with mutable properties.
- Default parameter values in C# records (e.g., `int Page = 1`) → F# class with default member values.

### SessionHelper static class
- Convert to an F# module with a let-bound function.

### Known F# gotchas (from prior phases)
- `TimeSpan.FromSeconds` needs `float` literals (e.g., `30.0` not `30`)
- `[<Extension>]` attribute pattern needed for C# interop extension methods (not applicable here since Api is the top-level consumer)
- F# `.fsproj` requires `<Compile Include>` in dependency order
- Solution file needs F# project GUID: `F2A71F9B-5D33-465A-A702-920D77279786`

## Implementation Units

### Unit 1: SignalR DTOs and Hub Client Interface

**Goal:** Port the shared DTO records and the `ISearchHubClient` interface that SearchHub and HubNotificationService both depend on.

**Files:**
- Create: `src/Ignite.Api/Hubs/SearchHub.fs`

**Approach:** Convert C# records to F# types. `ISearchHubClient` becomes an F# interface. DTO records (`SearchProgressUpdate`, `SearchResultUpdate`, etc.) can be simple F# types with primary constructors — they only need to serialize to JSON, not deserialize.

**Patterns to follow:** `Ignite.Core/Interfaces.fs` for interface definitions, `Ignite.Core/Entities.fs` for record-like types.

**Verification:** Compiles successfully.

### Unit 2: SearchHub

**Goal:** Port the SignalR hub class.

**Files:**
- Continue: `src/Ignite.Api/Hubs/SearchHub.fs` (append after DTOs)

**Approach:** `type SearchHub(logger: ILogger<SearchHub>) = inherit Hub<ISearchHubClient>()`. Override `OnConnectedAsync`/`OnDisconnectedAsync`. Port `JoinSearchSession`, `LeaveSearchSession`, `JoinJobUpdates`, `LeaveJobUpdates` as members.

**Verification:** Compiles successfully.

### Unit 3: HubNotificationService

**Goal:** Port the notification service.

**Files:**
- Create: `src/Ignite.Api/Hubs/HubNotificationService.fs`

**Approach:** Port `IHubNotificationService` interface and `HubNotificationService` class. Straightforward — all methods are simple wrappers around `IHubContext` calls.

**Patterns to follow:** `Ignite.Infrastructure/Spotify/SpotifyAuthService.fs` for interface implementation pattern.

**Verification:** Compiles successfully.

### Unit 4: Request DTOs and SessionHelper

**Goal:** Port the request DTO types and the `SessionHelper` static class used across multiple endpoints.

**Files:**
- Create: `src/Ignite.Api/Program.fs` (first section — types and helpers before the main entry point)

**Approach:**
- `SearchFromPlaylistRequest`, `ExportToPlaylistRequest`, `CdlcSearchRequest` need JSON deserialization. Use `[<CLIMutable>]` F# records or classes with default constructors.
- `SessionHelper.GetValidSessionAsync` → module-level `let` function or a static type member.

**Verification:** Compiles successfully.

### Unit 5: Program.fs — Service Configuration

**Goal:** Port the `WebApplication.CreateBuilder` setup, all `builder.Services.Add*` calls, Serilog, Sentry, OpenTelemetry, CORS, Hangfire, and DI registrations.

**Files:**
- Continue: `src/Ignite.Api/Program.fs`

**Approach:**
- Use `[<EntryPoint>] let main (args: string array) = ...` or a top-level module with main.
- All builder configuration is method-chaining which translates directly. Use `|> ignore` for void returns.
- Hangfire `SQLiteStorageOptions` with object initializer → named constructor args or post-construction assignment.
- Array literals: C# `["default", "scraping", "matching"]` → F# `[| "default"; "scraping"; "matching" |]`.

**Verification:** Compiles and app starts without errors.

### Unit 6: Program.fs — API Endpoints

**Goal:** Port all `app.MapGet`/`app.MapPost` endpoint definitions.

**Files:**
- Continue: `src/Ignite.Api/Program.fs`

**Approach:**
- Each minimal API endpoint lambda needs to work with ASP.NET's DI parameter injection. In F#, use `Func<>` delegates or handler functions.
- C# anonymous objects → F# anonymous records (`{| field = value |}`).
- LINQ `.Select(...)` → `Seq.map` or keep LINQ with `|> Seq.toList`.
- Null checks: `song is not null` → `not (isNull song)`.

**Verification:** All endpoints respond correctly (build + test suite passes).

### Unit 7: Project File and Solution Updates

**Goal:** Replace `.csproj` with `.fsproj`, update solution files, delete old C# source.

**Files:**
- Create: `src/Ignite.Api/Ignite.Api.fsproj`
- Modify: `Ignite.sln`, `Ignite.slnx`
- Delete: `src/Ignite.Api/Program.cs`, `src/Ignite.Api/Hubs/SearchHub.cs`, `src/Ignite.Api/Hubs/HubNotificationService.cs`, `src/Ignite.Api/Ignite.Api.csproj`

**Approach:**
- New `.fsproj` uses `Microsoft.NET.Sdk.Web`, same packages, `<Compile Include>` items in order: `Hubs/SearchHub.fs`, `Hubs/HubNotificationService.fs`, `Program.fs`.
- Drop `ImplicitUsings` (F# doesn't use it).
- Solution: change project type GUID to `F2A71F9B-5D33-465A-A702-920D77279786`, path to `.fsproj`.

**Verification:** `dotnet build` succeeds with 0 errors. `dotnet test` passes all 57 tests.

### Unit 8: Convert Ignite.Core.Tests to F#

**Goal:** Convert the trivial test project to F# to make the entire solution F#.

**Files:**
- Create: `tests/Ignite.Core.Tests/Ignite.Core.Tests.fsproj`
- Create: `tests/Ignite.Core.Tests/Tests.fs`
- Modify: `Ignite.sln`, `Ignite.slnx`
- Delete: `tests/Ignite.Core.Tests/UnitTest1.cs`, `tests/Ignite.Core.Tests/Ignite.Core.Tests.csproj`

**Approach:** Single xUnit test in F#. Use `open Xunit` and `[<Fact>]` attribute.

**Verification:** `dotnet test` passes all tests (57 matching + 1 core).

## Acceptance Criteria

- [ ] All 3 C# source files in Ignite.Api converted to F#
- [ ] `.csproj` replaced with `.fsproj` for both Ignite.Api and Ignite.Core.Tests
- [ ] Solution files updated with F# GUIDs
- [ ] `dotnet build` succeeds with 0 errors
- [ ] `dotnet test` passes all tests
- [ ] No C# source files remain in any `src/` project (only auto-generated in `obj/`)
- [ ] All API endpoints behave identically (no functional changes)
- [ ] Docker build succeeds

## Dependencies & Risks

- **Minimal API + F# parameter injection**: ASP.NET's minimal API parameter binding uses reflection that may not work identically with F# lambdas. May need `Func<>` wrappers or explicit `RequestDelegateFactory` usage. Mitigation: test each endpoint type early.
- **SignalR strong typing**: `Hub<ISearchHubClient>` should work but verify the F# interface is visible to SignalR's proxy generator.
- **Request body deserialization**: F# record types need `[<CLIMutable>]` for System.Text.Json deserialization with default constructor. Verify with integration tests or manual testing.

## Sources

- Prior migration PRs: Infrastructure (#42), Jobs, Core, Matching
- `Ignite.Jobs/Jobs.fs` — reference for F# patterns (task CE, Hangfire attributes, error handling)
- `Ignite.Infrastructure/DependencyInjection.fs` — reference for `[<Extension>]` and service registration
