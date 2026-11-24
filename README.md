# Garmin → PostgreSQL → Google Drive (Docker on a local computer or server)

English | [Русский](README.ru.md)

The collector retrieves the configured data categories from Garmin Connect twice a day (09:00 and 22:00 Moscow time):
daily metrics, intraday samples, and activities with exercise sets and FIT files.
It stores the data in PostgreSQL, exports CSV and FIT files to Google Drive, and backs up the database.

## Detailed documentation

- [Architecture, setup, and application logic](docs/ARCHITECTURE.md)
- [PostgreSQL data dictionary: every table, field, and relationship](docs/DATABASE.md)
- [Garmin endpoints and CSV export queries](docs/ENDPOINTS_AND_EXPORTS.md)
- [Development plan](ROADMAP.md)

## Database layout

| Schema | Contents | Purpose |
|---|---|---|
| `raw` | Unmodified Garmin responses (jsonb): `raw.daily` for daily data, `raw.activity` for activities | Source of truth. All other tables can be rebuilt without additional Garmin requests (`--reparse`) |
| `garmin` | Parsed tables and views | Analysis and export |
| `legacy` | Version 1 tables (`daily_metrics`, `sync_state`) | Moved here automatically; can be removed after verification |

**Daily metrics** — one row per day, keyed by `day`:

| Table | Metrics |
|---|---|
| `garmin.sleep` | Sleep start and end, stages (deep, light, REM, awake), score, sleep stress and heart rate, respiration, SpO2 |
| `garmin.heart` | Resting heart rate (daily and 7-day average), minimum/maximum heart rate, nightly and weekly HRV, status and baseline range |
| `garmin.stress_energy` | Stress (average, maximum, time by level), Body Battery (maximum, minimum, at wake-up, charged, drained) |
| `garmin.movement` | Steps and goal, distance, floors, calories (total, active, basal), intensity minutes, activity time, waking respiration |
| `garmin.training` | Training readiness, training status, acute and chronic load, running/cycling VO2 max, fitness age, endurance |
| `garmin.body` | Weight, BMI, body fat, muscle mass, bone mass, body water |
| `garmin.hydration` | Water intake, goal, sweat loss |

**Intraday samples** — keyed by timestamp: `hr_samples` (heart rate), `stress_samples`,
`body_battery_samples`, `respiration_samples`, `hrv_samples` (nightly HRV), `steps_15min`, `sleep_stages`.

**Activities** — keyed by `activity_id`:

| Table | Contents |
|---|---|
| `garmin.activities` | One row per activity: type, time, duration, distance, heart rate, speed, cadence, power, elevation gain, training effect, load |
| `garmin.activity_laps` | Laps and splits |
| `garmin.activity_hr_zones` | Time in heart rate zones |
| `garmin.strength_sets` | Strength sets: exercise, repetitions, weight (kg), rest |
| `garmin.activity_samples` | Second-by-second data: heart rate, speed, cadence, power, elevation, coordinates |
| `garmin.activity_files` | Downloaded FIT files |

**Export views:** `garmin.daily_overview` combines all daily tables into one row per day,
including activity counts. `garmin.strength_log` includes exercise sets with activity dates and names.

Activity child tables reference `garmin.activities` with `ON DELETE CASCADE`.
Timestamps are stored as `timestamptz` and exported to CSV in Moscow time.

## Google Drive output (`RCLONE_REMOTE` folder)

```text
garmin_daily_metrics.csv        ← garmin.daily_overview
garmin_activities.csv
garmin_strength_sets.csv        ← garmin.strength_log
activities/  garmin_activity_laps.csv, garmin_activity_hr_zones.csv, garmin_activity_samples.csv
intraday/    garmin_hr.csv, garmin_stress.csv, garmin_body_battery.csv, garmin_respiration.csv,
             garmin_hrv_night.csv, garmin_steps_15min.csv, garmin_sleep_stages.csv
fit/         original activity files from the watch (ZIP archives containing FIT files)
backups/     pg_dump backups for the last 14 days
```

## Sync behavior

- The first version 2 run reprocesses the entire history, starting at the earliest day in the database
  (or `BACKFILL_FROM`). 16 daily endpoint requests per date and up to 6 per activity, with delays.
  A 90-day history takes approximately 20–40 minutes.
- Subsequent runs reload the most recent `RESYNC_DAYS` days and their activities:
  Garmin may sync data with a delay, and set weights can be edited retroactively.
- HTTP 429 (too many requests): wait 10 minutes and retry once. A repeated limit stops
  that sync phase; later runs resume with the checkpoint overlap.
- Availability depends on Garmin and the connected device. Missing metrics generally produce empty
  fields; failed requests can overwrite saved daily data in the current implementation. See the
  known limitations in the architecture document.

## Commands

```bash
docker compose up -d --build                               # start / update
docker compose run --rm collector python sync.py --login   # Garmin login (email, password, MFA code)
docker compose run --rm collector python sync.py --once    # run once manually
docker compose run --rm collector python sync.py --reparse # rebuild tables from raw.*, without Garmin requests
tail -f logs/sync.log                                      # view the log
```

## Database access from the local computer or server

Use `PG_PASSWORD` from `.env`:

```text
psql postgresql://garmin:<PG_PASSWORD>@127.0.0.1:5432/garmin
```

## Configuration

`.env` contains the database password, `tokens/` stores Garmin authentication tokens,
and `rclone/` contains Google Drive connection settings. These paths are excluded through `.gitignore`.
