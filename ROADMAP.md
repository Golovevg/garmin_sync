# Development plan

Each item is implemented in a separate commit. This document describes planned work;
the current application does not yet implement the setup flow below.

## Initial setup and credential storage

- On first launch, detect missing credentials and guide the user through interactive setup.
- Ship source code, releases, and container images without real credentials or embedded account access.
- The user supplies Garmin credentials and completes MFA when required. Store the resulting
  authentication tokens for subsequent runs; do not persist the Garmin account password.
- Guide the user through Google Drive authorization and destination selection. Store the resulting
  connection configuration and tokens locally within the application's persistent storage.
- Prompt for any other required secrets, including the database password, when no saved value exists.
- Hide secret input and exclude credentials from logs, error messages, exports, and Git history.
- Persist secrets separately from source code in application-managed storage that survives restarts
  and container rebuilds. Restrict filesystem access to the application owner.
- Reuse saved access on later launches. Prompt again when access expires, is revoked, or is removed.
- Provide a way to replace credentials and disconnect an account without deleting collected fitness data.
- Keep unattended scheduled runs non-interactive: report that setup or renewed authorization is
  required rather than waiting indefinitely for input. Provide an explicit interactive setup command.
- Verify first launch, restart with saved access, missing credentials, rejected authorization,
  credential replacement, and absence of credentials from tracked files and logs.

## Sync reliability fixes

1. Preserve previously saved daily responses and metrics when Garmin requests fail.
2. Check database dump success before accepting a backup or removing older backups.
3. Do not advance the activity sync checkpoint when retrieving the activity list fails.
4. Retry incomplete older activities, including missing sets, laps, and FIT files.
5. Replace ambiguous set-weight unit detection with a verified conversion.
6. Reconcile intraday samples after Garmin corrects the source data.
