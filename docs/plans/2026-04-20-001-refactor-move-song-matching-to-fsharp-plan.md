---
title: "refactor: Move SongMatchingService to F#"
type: refactor
status: completed
date: 2026-04-20
---

# refactor: Move SongMatchingService to F#

## Overview

Port the Spotify/CDLC matching logic (`SongMatchingService`) from C# to F# in a new `Ignite.Matching` project. The matching logic is a 9-strategy waterfall of pure string transforms and Spotify API queries — ideal for F#'s functional style. The existing `ISongMatchingService` interface stays in C# (`Ignite.Core`) as the interop boundary.

## Problem Statement / Motivation

The matching logic is inherently functional: stateless string normalization, a strategy pipeline evaluated lazily, and pattern-based decisions. C# requires boilerplate (`partial class` for source-generated regex, mutable dictionaries, imperative loops) that obscures the algorithm. F# expresses this more naturally with:

- Module-level compiled regex as `let` bindings
- Immutable `Map` literals for contraction dictionaries
- `seq { }` computation expressions for the lazy strategy pipeline
- Pattern matching for guard conditions

This is also the first step toward the shared infrastructure goal of F# as the backend language.

## Proposed Solution

Create `Ignite.Matching` (F# class library, `net10.0`) implementing `ISongMatchingService`. Write characterization tests against the C# implementation first, then port to F# and verify the same tests pass.

## Technical Approach

### Architecture

```
Ignite.Api  →  Ignite.Core
            →  Ignite.Infrastructure  →  Ignite.Core
                                      →  Ignite.Matching  →  Ignite.Core
            →  Ignite.Jobs            →  Ignite.Core
                                      →  Ignite.Infrastructure
Ignite.Matching.Tests  →  Ignite.Matching
                       →  Ignite.Core
```

- `Ignite.Matching` references only `Ignite.Core` (for `ISongMatchingService`, `ISpotifyClientService`, `Song`, `SpotifyTrack`, `MatchResult`)
- `Ignite.Infrastructure` gains a `ProjectReference` to `Ignite.Matching` and registers the F# implementation in `DependencyInjection.cs`
- `Ignite.Matching.Tests` is a new F# test project using xUnit v3 (`dotnet new xunit3 --language F#`)

### Implementation Phases

#### Phase 1: Characterization Tests

Write tests against the existing C# `SongMatchingService` to establish a behavioral baseline.

**Files to create:**
- `backend/tests/Ignite.Core.Tests/SongMatchingServiceTests.cs`

**Test coverage:**
1. `RemoveFeaturingArtists` — all patterns: `ft.`, `feat.`, `featuring`, `&`, `and` (currently private; test via `GetSearchStrategies` output or temporarily make `internal` with `InternalsVisibleTo`)
2. `RemoveParenthetical` — parentheses, brackets, braces; multiple groups; nested
3. `ExpandContractions` — all 35 contractions, case insensitivity, word boundaries
4. `ContractExpansions` — all 14 expansions, case insensitivity, word boundaries
5. `GetSearchStrategies` output sequence for known inputs:
   - Standard case (artist + title + album)
   - Artist with featuring (`"Artist ft. Someone"`)
   - Artist with pipe (`"Name | Имя"`)
   - Title with parenthetical (`"Song (Live)"`)
   - Title with contractions (`"Don't Stop"`)
   - All guards firing (clean artist == artist, etc.)
6. `FindSpotifyMatchAsync` — strategy waterfall (mock `ISpotifyClientService`)
7. `MatchSongsToSpotifyAsync` — batch iteration, progress reporting, hardcoded `"found"` strategy string

**Approach for testing private helpers:** Add `[assembly: InternalsVisibleTo("Ignite.Core.Tests")]` to `Ignite.Core` and change helpers from `private` to `internal` temporarily. After the C# implementation is deleted, remove this attribute.

- Estimated effort: 2-3 hours

#### Phase 2: F# Project Setup

**Files to create:**
- `backend/src/Ignite.Matching/Ignite.Matching.fsproj`
- `backend/src/Ignite.Matching/StringNormalization.fs`
- `backend/src/Ignite.Matching/SearchStrategies.fs`
- `backend/src/Ignite.Matching/SongMatchingService.fs`
- `backend/tests/Ignite.Matching.Tests/Ignite.Matching.Tests.fsproj`

**Solution file update:** Add with F# project type GUID `{F2A71F9B-5D33-465A-A702-920D77279786}`.

**`.fsproj` contents:**
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="..\Ignite.Core\Ignite.Core.csproj" />
  </ItemGroup>
  <ItemGroup>
    <Compile Include="StringNormalization.fs" />
    <Compile Include="SearchStrategies.fs" />
    <Compile Include="SongMatchingService.fs" />
  </ItemGroup>
</Project>
```

**File ordering is significant** — F# compiles top-to-bottom. `StringNormalization.fs` has no dependencies, `SearchStrategies.fs` depends on it, and `SongMatchingService.fs` depends on both.

**Solution file:** Run `dotnet sln backend/Ignite.sln add backend/src/Ignite.Matching/Ignite.Matching.fsproj` — the CLI detects F# and writes the correct project type GUID automatically.

- Estimated effort: 30 minutes

#### Phase 3: F# Implementation

**`StringNormalization.fs`** — Pure functions module:
```fsharp
module Ignite.Matching.StringNormalization

// Compiled regex (module-level, cached):
// - featuringRegex: \s*(ft\.?|feat\.?|featuring|\s&\s|\sand\s)\s*.*$
// - parentheticalRegex: \s*[\(\[\{].*?[\)\]\}]\s*

// Functions:
// val removeFeaturingArtists: string -> string
// val removeParenthetical: string -> string
// val expandContractions: string -> string
// val contractExpansions: string -> string
```

Key decisions:
- Use `Regex("pattern", RegexOptions.Compiled ||| RegexOptions.IgnoreCase)` as module-level `let` bindings — initialized once at module load (equivalent to `static readonly` in C#). No `[GeneratedRegex]` equivalent exists in F#; compiled regex with static lifetime is the closest match.
- Contraction/expansion dictionaries as immutable `Map<string, string>` literals (or `dict []` for `IDictionary` if iteration order doesn't matter)
- `expandContractions`/`contractExpansions` use `Regex.Replace` with `\b` word boundaries and `RegexOptions.IgnoreCase` — identical to the C# approach
- `RemoveParenthetical` regex uses lazy `.*?` matching one pair at a time — replicate exactly, do not "fix" to greedy or multi-match (preserves behavior for titles like `"Song (Remix) [Live]"`)

**`SearchStrategies.fs`** — Strategy pipeline:
```fsharp
module Ignite.Matching.SearchStrategies

// val getSearchStrategies: artist:string -> title:string -> album:string option -> (string * string) seq
```

Key decisions:
- `seq { }` computation expression for lazy evaluation (mirrors C# `yield return`)
- `album` parameter typed as `string option` internally, converted from nullable at the interface boundary
- Exact same guard conditions: `cleanArtist <> artist`, `pipeParts.Length > 1`, etc.
- No deduplication of strategies (preserves existing behavior)

**`SongMatchingService.fs`** — Interface implementation:
```fsharp
namespace Ignite.Matching

open System.Threading
open System.Threading.Tasks
open Ignite.Core.Entities
open Ignite.Core.Interfaces
open Microsoft.Extensions.Logging

type SongMatchingService(spotifyClient: ISpotifyClientService, logger: ILogger<SongMatchingService>) =
    interface ISongMatchingService with
        member _.FindSpotifyMatchAsync(accessToken, artist, title, album, ct) =
            task {
                let strategies = SearchStrategies.getSearchStrategies artist title (Option.ofObj album)
                for (query, strategyName) in strategies do
                    if not (System.String.IsNullOrWhiteSpace query) then
                        try
                            let! result = spotifyClient.SearchTrackAsync(accessToken, query, ct)
                            if result <> null then
                                logger.LogDebug("Found match for '{Artist} - {Title}' using strategy '{Strategy}'", artist, title, strategyName)
                                return result
                        with ex ->
                            logger.LogWarning(ex, "Search failed for query '{Query}'", query)
                logger.LogDebug("No Spotify match found for '{Artist} - {Title}'", artist, title)
                return null
            }

        member this.MatchSongsToSpotifyAsync(accessToken, songs, progress, ct) =
            task {
                let songList = songs |> Seq.toList
                let results = System.Collections.Generic.List<MatchResult>()
                let mutable processed = 0
                for song in songList do
                    ct.ThrowIfCancellationRequested()
                    let! matchResult = (this :> ISongMatchingService).FindSpotifyMatchAsync(accessToken, song.Artist, song.Title, song.Album, ct)
                    results.Add(MatchResult(song, matchResult, (if matchResult <> null then "found" else null)))
                    processed <- processed + 1
                    if progress <> null then progress.Report(processed)
                return results :> System.Collections.Generic.IReadOnlyList<MatchResult>
            }
```

Key decisions:
- **Use `task {}` CE** (not `async {}`) — returns `Task<T>` directly, matching the C# interface. No `Async.StartAsTask` conversion needed. Better performance (same state machine as C# async).
- Concrete class (required for DI registration via `services.AddScoped`)
- `album` nullable-to-option conversion at the boundary: `Option.ofObj album`
- `MatchSongsToSpotifyAsync` hardcodes `"found"` in `MatchResult.MatchStrategy` (preserves existing behavior)
- `CancellationToken` only passed to `SearchTrackAsync`, not checked in `FindSpotifyMatchAsync` (preserves existing behavior)
- `try/with` per strategy call (preserves existing exception handling)
- `null` returns for `SpotifyTrack?` — at the C# interface boundary, F# must return `null` not `None`

- Estimated effort: 2-3 hours

#### Phase 4: DI Registration and Wiring

**Files to modify:**
- `backend/src/Ignite.Infrastructure/Ignite.Infrastructure.csproj` — add `ProjectReference` to `Ignite.Matching`
- `backend/src/Ignite.Infrastructure/DependencyInjection.cs` — change `SongMatchingService` registration to F# type

```csharp
// Before:
services.AddScoped<ISongMatchingService, Ignite.Core.Services.SongMatchingService>();

// After:
services.AddScoped<ISongMatchingService, Ignite.Matching.SongMatchingService>();
```

DI lifetime: **Scoped** (matches existing registration).

- Estimated effort: 15 minutes

#### Phase 5: Port Tests and Validate

**Files to create:**
- `backend/tests/Ignite.Matching.Tests/StringNormalizationTests.fs`
- `backend/tests/Ignite.Matching.Tests/SearchStrategiesTests.fs`
- `backend/tests/Ignite.Matching.Tests/SongMatchingServiceTests.fs`

Port the Phase 1 characterization tests to F# targeting the new implementation. All tests must produce identical results to the C# baseline.

- Estimated effort: 1-2 hours

#### Phase 6: Cleanup

**Files to delete:**
- `backend/src/Ignite.Core/Services/SongMatchingService.cs`
- `backend/src/Ignite.Core/Services/` directory (if empty)

**Files to modify:**
- Remove `InternalsVisibleTo` from `Ignite.Core` (added in Phase 1)
- Remove Phase 1 C# characterization tests from `Ignite.Core.Tests` (now superseded by F# tests)
- Update `Ignite.sln` to include the two new F# projects

**Verify:**
- `dotnet build` succeeds for entire solution
- `dotnet test` passes all tests
- Application starts successfully (`dotnet run --project backend/src/Ignite.Api`)

- Estimated effort: 30 minutes

## System-Wide Impact

- **Interaction graph**: `UpdateSpotifyIdsJob` → `ISongMatchingService.FindSpotifyMatchAsync` → `ISpotifyClientService.SearchTrackAsync`. No change to the call chain — only the concrete type behind the interface changes.
- **Error propagation**: Exceptions from `SearchTrackAsync` are caught per-strategy and logged as warnings. Same behavior in F# via `try/with`.
- **State lifecycle risks**: None. `SongMatchingService` is stateless. All persistence is handled by the caller (`UpdateSpotifyIdsJob` via `ISongRepository`).
- **API surface parity**: The `ISongMatchingService` interface is unchanged. No other consumers exist.
- **Log category change**: Logger category changes from `Ignite.Core.Services.SongMatchingService` to `Ignite.Matching.SongMatchingService`. Any Loki queries filtering on the old category will need updating.

## Acceptance Criteria

- [ ] Characterization tests written and passing against C# implementation
- [ ] `Ignite.Matching` F# project created with correct project structure
- [ ] All 4 normalization helpers ported to F# with identical behavior
- [ ] 9-strategy waterfall produces identical query sequence for all test inputs
- [ ] `FindSpotifyMatchAsync` and `MatchSongsToSpotifyAsync` implemented in F#
- [ ] DI registration updated in `Ignite.Infrastructure`
- [ ] F# test project passes all characterization tests
- [ ] Solution builds cleanly (`dotnet build`)
- [ ] All tests pass (`dotnet test`)
- [ ] Application starts and Hangfire job can be triggered successfully
- [ ] C# implementation removed from `Ignite.Core`

## Success Metrics

- All existing characterization tests pass against the F# implementation
- Match rate is unchanged (same Spotify results for same inputs)
- No regression in Hangfire job execution time

## Dependencies & Risks

**Dependencies:**
- .NET 10 SDK must support F# (confirmed: F# 10.0 / FSharp.Core ships with .NET 10)
- xUnit v3 supports F# test projects (`dotnet new xunit3 --language F#`)

**Risks:**
- **Subtle regex differences**: Mitigated by characterization tests covering edge cases. F# has no `[GeneratedRegex]` but module-level `Regex(..., Compiled)` is functionally equivalent.
- **Nullable reference type friction**: C# interface uses `string?` for album and CancellationToken defaults. F# with `<Nullable>enable</Nullable>` uses `string | null` syntax at boundaries; convert to `Option` internally with `Option.ofObj`. At return boundaries, F# must return `null` (not `None`) for `SpotifyTrack?`.
- **Silent match rate regression**: Mitigated by testing strategy sequence output for known inputs. A post-deploy check comparing match counts before/after is recommended.
- **Log query breakage**: Logger category name changes from `Ignite.Core.Services.SongMatchingService` to `Ignite.Matching.SongMatchingService`. Update any Grafana Loki queries filtering on the old category.
- **`task {}` early-return pattern**: F# `task {}` does not support early `return` from inside a `for` loop the same way C# does. The implementation may need a mutable `found` flag or restructuring using `Seq.tryPick` with async. Test carefully that the waterfall short-circuits correctly.

## Sources & References

### Internal References

- Current implementation: `backend/src/Ignite.Core/Services/SongMatchingService.cs`
- Interface: `backend/src/Ignite.Core/Interfaces/ISongMatchingService.cs`
- DI registration: `backend/src/Ignite.Infrastructure/DependencyInjection.cs`
- Hangfire job (caller): `backend/src/Ignite.Jobs/Jobs/UpdateSpotifyIdsJob.cs`
- Known matching bug: `docs/debug/babymonster-drip-matching-issue.md` (bidirectional Contains issue — not in scope but relevant context)

### Related Work

- Previous plan: `docs/plans/2026-03-23-001-fix-match-results-discoverability-beta-plan.md`
