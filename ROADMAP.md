# Fixes organized by commit

English | [Русский](ROADMAP.ru.md)

Status: planned; implementation of these fixes has not started. Original v2 and documentation
have already been committed separately. The order below is the recommended implementation sequence.
Each commit includes regression checks and updates the relevant English and Russian documentation.

## Target data flow

Garmin → original JSON responses and activity archives in PostgreSQL → parsed tables →
CSV and original-file exports from PostgreSQL → Google Drive.

PostgreSQL holds all collected training data, including ZIP/FIT bytes. Export directories are
rebuildable from the database. Credentials and configuration live separately in persistent local
application storage, outside source code, Git, container images, and exported data.
The application runs on a local computer or server; scheduled execution remains non-interactive.

## Implementation sequence

| No. | Commit message | Change and outcome | Required verification |
|---|---|---|---|
| 01 | `fix: reject failed database backups before rotation` | Replace the unchecked shell pipeline with separately checked processes and timeouts. Keep passwords out of logs and process arguments. Write a temporary dump, publish only on success, retain previous backups on failure, avoid filename collisions, and explicitly separate local file-count retention from remote age retention. | Connection/pg_dump failure, compression failure, disk-full and timeout cannot produce a successful backup or rotate old copies. Restore a successful dump into an isolated test database. |
| 02 | `feat: add versioned PostgreSQL schema migrations` | Add a schema version registry and ordered, transactional, locked migrations for empty databases and existing v2 installations. Preserve current and legacy data; CREATE TABLE IF NOT EXISTS is not a column migration mechanism. | Fresh initialization, migration of a v2 copy, repeated startup, rollback of a failed migration, and concurrent migration exclusion. |
| 03 | `fix: preserve collected data on Garmin request failures` | Distinguish success, valid absence, unsupported methods, and transient failures. Track request status/errors separately from payloads. Preserve raw and parsed values when sources fail; refresh fetch timestamps only for responses actually obtained. Save available components without discarding previous unavailable components. | A failed/partially failed repeat preserves saved sleep and HRV. Valid zero remains zero; valid empty results differ from network failures. |
| 04 | `fix: prevent sync checkpoints from skipping failed data` | Do not treat an activity-list failure as a successful empty list. Advance checkpoints only for confirmed processing. Retry unfinished dates/requests even outside RESYNC_DAYS, retain incremental collection, and define inclusive window boundaries explicitly. | List failure leaves checkpoint unchanged; legitimate empty list succeeds; old gaps are retried after newer dates advance; interruption/restart loses no data. |
| 05 | `fix: retry incomplete historical activity data` | Track completion by activity endpoint and original download. Retry incomplete older known IDs. Distinguish unsupported device categories from transient errors to avoid infinite impossible retries. | Reload missing sets, laps, detail samples and originals independently; avoid unnecessary repeat downloads for complete activities. |
| 06 | `fix: convert strength weights using verified source units` | Verify actual raw responses and the library contract; remove the 1000 threshold. Convert confirmed source units, retain raw values, do not guess unknown units, and support targeted reparse of affected sets. | Verified examples for zero, 500 g, 1000 g, normal working weight, fractional values, missing weight and unknown units; repeated reparse is consistent. |
| 07 | `fix: preserve timestamp offsets during parsing and export` | Parse UTC, Z, explicit offsets and fractions correctly; convert instants instead of replacing tzinfo. Distinguish local activity start, absolute instant, and activity date; document CSV timezone semantics. | Equivalent offset timestamps produce the same instant; preserve fractions; cover midnight boundaries, naive local times and invalid strings. |
| 08 | `fix: reconcile corrected intraday intervals safely` | Transactionally replace a successfully fetched day/source interval set, removing obsolete samples. Never clear data on request failure; handle sleep spanning midnight and neighboring days. | Corrected sleep/sample intervals replace old ones without duplicates; failures preserve data and adjacent intervals remain intact. |
| 09 | `feat: persist original activity archives in PostgreSQL` | Add compatible fields to garmin.activity_files for bytea content, SHA-256, actual content format/type, byte length, download time and verified completeness. Validate and commit new originals to the database before writing export copies. Temporarily allow old metadata-only rows. | Validate ZIP/FIT readability and format; reject corrupt/unexpected responses. Bytes and SHA-256 match after database readback; retries do not duplicate; failed writes never mark completion. |
| 10 | `feat: import existing activity archives into PostgreSQL` | Add a resumable import command for existing out/fit files. Match activities using verified information and the manifest, not filenames alone. Report ambiguous, missing and corrupt inputs; queue missing originals for retrieval. | Dry run, repeat run, interruption, length/hash mismatch, ambiguous IDs and missing files. Metadata-only rows remain incomplete; never delete source files. |
| 11 | `refactor: export original activity files from PostgreSQL` | Make the database the source of exported originals. Recreate out/fit atomically from stored bytes and verify SHA-256. File presence no longer defines storage completeness. Switch export flow after verifying the import. | Delete a test export directory and rebuild it without Garmin. Restore the full database dump and recover originals with identical hashes. |
| 12 | `fix: make exports and Drive transfers resumable` | Stream large query results instead of fetchall while retaining atomic file replacement. Track each export/upload status; add bounded retries and timeouts. Report partial/cleanup failures honestly and retry delivery without recollecting Garmin. Do not add mirroring that deletes user files. | Large-history exports use bounded memory; interrupted writes/transfers retain the last complete copy and explicit failure state; retry does not require recollection. |
| 13 | `fix: prevent overlapping collectors and rebuilds` | Use a coordinated PostgreSQL lock for scheduled/manual sync and reparse. Validate date ranges, schedules and retention settings at startup. | Second writer exits/reports contention; crash releases the lock; invalid settings are rejected before collection. |
| 14 | `feat: bootstrap local configuration before database startup` | Add a host-side first-start command. Prompt for missing required settings with hidden secret input, atomically persist them in an owner-restricted application directory, then start PostgreSQL and the collector. Pass database passwords separately from the URI or encode them properly. Do not rotate an existing database password merely by editing .env. | Fresh install, repeat start without prompts, special-character passwords, existing database, cancelled setup; no secrets in Git, logs, argv or exports. |
| 15 | `feat: guide Garmin and Google Drive account authorization` | Integrate Garmin login/MFA and Google Drive authorization/folder selection into setup. Provide an explicit other-device authorization flow for a headless server. Persist tokens locally, not the Garmin password; verify persistence and access. Support reauthorization, replacement and disconnect without deleting fitness data. Scheduled mode never prompts. | Successful/rejected OAuth and MFA, expired/revoked tokens, persistence failure, restart and headless operation; actionable status without hangs or secret leakage. |
| 16 | `build: pin dependencies and align PostgreSQL tooling` | Pin verified Python packages and base images, align pg_dump with PostgreSQL 16, remove unused dependencies after verification, and document updates and supported local-computer/server environments. | Reproducible build, client/server version checks, imports, CLI execution, dump creation and restore. |
| 17 | `test: verify complete sync backup and recovery lifecycle` | Add the final integration scenario and a safe existing-installation upgrade procedure. Update schema/field documentation in both languages to reflect implemented behavior. | Isolated environment: setup → collection → gap recovery → originals in DB → CSV/Drive adapter → backup → empty-database restore → file recovery. Compare row counts, date coverage, bytes and archive hashes. |

## Dependencies and existing-installation transition

- Complete 01 before migrations and verify restoration of a current database copy before upgrading.
- 02 supports schema changes in 03–05 and 09–10. Add tables/columns without dropping existing data.
- 03 precedes 04, 05 and 08: distinguish unavailable data from failed requests first.
- Archive transition is 09 → 10 → 11. Until import is verified, preserve both database backups and
  existing files. A corrected backup of the old schema still does not include archive bytes.
- Before 11, filename/length metadata alone does not constitute stored originals. Old dumps cannot
  recover missing archives; surviving copies or Garmin downloads are needed.
- On a fresh installation, 14 executes before services start and 15 uses its persistent configuration
  storage. This describes runtime setup order, not a requirement to implement setup before reliability fixes.
- Reparse repairs only retained responses. Missing/overwritten responses require another Garmin request.
  Verify unit/time corrections against a database copy first.
- GitHub commits do not automatically update the production server. Prepare a separate rollout with
  backup, migrations, archive import, verification and a rollback procedure.

## Execution rules

- One number is one reviewable task/commit; split larger items further when needed while retaining dependencies.
- Include regression tests with each fix; item 17 does not defer them.
- Tests use sanitized fixtures and isolated PostgreSQL, not production data. Verify real Garmin/Drive
  access separately; mocked delivery is not represented as a successful external upload.
- Check for credentials before publication; never request credentials in chat.
- Defer destructive removal of old schema/data until complete migration has been verified; it is outside this plan.
