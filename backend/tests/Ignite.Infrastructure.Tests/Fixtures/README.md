# Frozen legacy schema fixture

`legacy-schema-v1.sql` contains schema only, no production records or credentials.
It replays the public legacy sequence: original tables/indexes and FTS definitions,
then the later `official_dlc` addition and saved-playlist table/index creation.
It is deliberately not generated from the current EF model or loaded from the new
migration catalogue, so future model changes cannot silently redefine the legacy input.

The owner-approved November 3, 2026 read-only metadata inventory established fingerprint
`91520ea3d23a8c812dea171d9bf5194e5f896069b3b540ffbab723e7b2ffa6a5`.
The fixture and the initial draft migration independently reproduce that fingerprint.
`legacy-rows-v1.sql` seeds only synthetic rows using the frozen old schema before
adoption. Current repositories read them after adoption and any pending upgrade, so
future model changes cannot accidentally redefine the historical seed format.
Raw inventory evidence remains private; the fixture's identifiers and literal values
are already part of the public application source.

Preserve the intentional SQL layout. SQLite retains statement text, including the
whitespace before the standalone index terminator. That terminator reproduces the
legacy definition without putting trailing whitespace in this source file. No schema
fingerprint normalization or relaxed matching is used.

This is an unjournaled legacy fixture, not an instruction to replay legacy DDL in
production. No database adoption has been performed. The first migration is still an
unmerged, unactivated draft; once applied to persistent deployed data, its identifier
and exact SQL bytes are immutable.
