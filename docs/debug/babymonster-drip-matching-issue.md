# BABYMONSTER "DRIP" Matching Issue - Root Cause Analysis

**Date:** 2026-01-04
**Status:** Root cause identified

## Summary

The song "DRIP" by BABYMONSTER exists in the CustomsForge/Ignition database and Spotify returns correct matching data, but the application fails to find a match in production.

## Root Cause

**The EF Core LibSQL provider does not correctly translate the `constantString.Contains(dbColumn)` pattern in the search query.**

### Problematic Code

`backend/src/Ignite.Infrastructure/Data/Repositories/SongRepository.cs:46-57`:

```csharp
if (!string.IsNullOrWhiteSpace(filter.Artist))
{
    var artistLower = filter.Artist.ToLowerInvariant();
    // Problem: second part of OR is not translatable
    query = query.Where(s =>
        s.Artist.ToLower().Contains(artistLower) ||    // ✅ Works
        artistLower.Contains(s.Artist.ToLower())       // ❌ Fails
    );
}

if (!string.IsNullOrWhiteSpace(filter.Title))
{
    var titleLower = filter.Title.ToLowerInvariant();
    // Same problem here
    query = query.Where(s =>
        s.Title.ToLower().Contains(titleLower) ||      // ✅ Works
        titleLower.Contains(s.Title.ToLower())         // ❌ Fails
    );
}
```

### Why It Fails

1. `s.Artist.ToLower().Contains(artistLower)` - Column contains constant - translates to `LOWER(artist) LIKE '%' || @p || '%'`
2. `artistLower.Contains(s.Artist.ToLower())` - Constant contains column - **NOT properly translatable**

EF Core 9 with the BMDRM.LibSql provider either:
- Throws an exception (killing the entire query)
- Translates it incorrectly (producing SQL that returns unexpected results)
- Falls back to client evaluation (extremely slow, may timeout)

## Evidence

### 1. Song Exists in Production Database

Query against Turso production database:
```sql
SELECT Id, Artist, Title, Album FROM Songs WHERE Id = 64419
```

Result:
| Id | Artist | Title | Album |
|----|--------|-------|-------|
| 64419 | BABYMONSTER | DRIP | DRIP |

Hex verification confirms clean ASCII with no hidden characters:
- Artist hex: `424142594D4F4E53544552` = "BABYMONSTER" (11 chars)
- Title hex: `44524950` = "DRIP" (4 chars)

### 2. Spotify Returns Correct Data

Spotify API search for "BABYMONSTER DRIP" returns:
```json
{
  "name": "DRIP",
  "artists": [{"name": "BABYMONSTER"}],
  "album": {"name": "DRIP"},
  "id": "198zDKzyktXRG1PGpidY9h"
}
```

### 3. Raw SQL Queries Work

Direct SQL query against Turso succeeds:
```sql
SELECT COUNT(*) FROM songs
WHERE LOWER(artist) LIKE '%babymonster%'
  AND LOWER(title) LIKE '%drip%'
-- Returns: 1
```

EF Core-style query with `instr()` also works:
```sql
SELECT COUNT(*) FROM songs
WHERE (LOWER(artist) LIKE '%babymonster%' OR instr('babymonster', LOWER(artist)) > 0)
  AND (LOWER(title) LIKE '%drip%' OR instr('drip', LOWER(title)) > 0)
-- Returns: 1
```

### 4. Local Database is Empty (Not the production issue)

The local `ignite.db` has 0 songs - this would cause issues in local dev but the user confirmed this is a production issue.

## Technical Details

### Database Configuration

- **Production:** Turso (LibSQL) via `BMDRM.LibSql.Core` v9.0.10
- **Local:** SQLite via `Microsoft.EntityFrameworkCore.Sqlite` v9.0.6
- **Connection:** `libsql://ignite-for-spotify-2-scowalt.aws-us-west-2.turso.io`

### Search Flow

1. User selects Spotify playlist
2. `Program.cs:618-641` fetches tracks from Spotify
3. For each track, creates `SongSearchFilter` with artist and title
4. Calls `songRepo.SearchAsync()` which builds the problematic EF Core query
5. Query fails or returns no results due to translation issue

### Relevant Files

| File | Purpose |
|------|---------|
| `backend/src/Ignite.Infrastructure/Data/Repositories/SongRepository.cs` | Contains the problematic search query |
| `backend/src/Ignite.Api/Program.cs:587-699` | Search endpoint that calls the repository |
| `backend/src/Ignite.Infrastructure/DependencyInjection.cs` | Database provider configuration |

## Related Issues

- [EF Core #21086 - Where Any + Contains is not translated](https://github.com/dotnet/efcore/issues/21086)
- [EF Core #22917 - Sqlite: Should string.Contains use LIKE?](https://github.com/dotnet/efcore/issues/22917)
- [SQLite Provider Limitations](https://learn.microsoft.com/en-us/ef/core/providers/sqlite/limitations)

## Recommended Fix

Replace the bidirectional Contains pattern with a unidirectional LIKE pattern that EF Core can reliably translate:

```csharp
// Option 1: Only use column.Contains(constant) - simpler but loses bidirectional matching
query = query.Where(s => s.Artist.ToLower().Contains(artistLower));

// Option 2: Use raw SQL for the bidirectional check
query = query.Where(s =>
    EF.Functions.Like(s.Artist.ToLower(), $"%{artistLower}%") ||
    EF.Functions.Like(artistLower, $"%{s.Artist.ToLower()}%")
);

// Option 3: Use the FTS5 full-text search instead (already implemented)
// See SongRepository.FullTextSearchAsync()
```

## Verification Steps

To verify this fix works:
1. Enable EF Core SQL logging to see generated queries
2. Test with "BABYMONSTER" + "DRIP" specifically
3. Confirm the query returns the expected result (Id: 64419)

## Additional Notes

- The FTS5 full-text search (`SongRepository.FullTextSearchAsync`) is an alternative that bypasses this issue entirely
- The matching logic was designed for flexibility (handling cases where DB has partial artist name) but the implementation has translation issues
- Total songs in production database: ~71,809
