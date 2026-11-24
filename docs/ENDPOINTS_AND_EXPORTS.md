# Garmin inputs and exported files

## Daily endpoints

`fetch_day()` calls these methods sequentially with an ISO date. Availability depends on the
Garmin account, device, API, and installed `garminconnect` version. This is the implemented
endpoint set, not a guarantee of every Garmin data category.

| Raw endpoint name | Library method |
|---|---|
| `user_summary` | `get_user_summary(day)` |
| `heart_rates` | `get_heart_rates(day)` |
| `hrv` | `get_hrv_data(day)` |
| `respiration` | `get_respiration_data(day)` |
| `spo2` | `get_spo2_data(day)` |
| `max_metrics` | `get_max_metrics(day)` |
| `sleep` | `get_sleep_data(day)` |
| `stress` | `get_stress_data(day)` |
| `body_battery` | `get_body_battery(day)` |
| `steps` | `get_steps_data(day)` |
| `training_readiness` | `get_training_readiness(day)` |
| `training_status` | `get_training_status(day)` |
| `hydration` | `get_hydration_data(day)` |
| `body_composition` | `get_body_composition(day)` |
| `fitness_age` | `get_fitnessage_data(day)` |
| `endurance_score` | `get_endurance_score(day)` |

## Activity endpoints

| Stored raw endpoint | Input / method |
|---|---|
| `list` | Item returned by `get_activities_by_date(start, end)` |
| `summary` | `get_activity(activity_id)` |
| `splits` | `get_activity_splits(activity_id)` |
| `hr_zones` | `get_activity_hr_in_timezones(activity_id)` |
| `exercise_sets` | `get_activity_exercise_sets(activity_id)` |
| `details` | `get_activity_details(activity_id)` |

Exercise sets are requested for `strength_training`, `hiit`, `indoor_cardio`, or
`fitness_equipment`, or when the list item reports total/active sets. Original activity
files are downloaded separately using `download_activity` when `DOWNLOAD_FIT=1`.
Binary files are not stored in `raw.activity`.

## Export queries

The CSV header comes directly from each SQL result. All files are regenerated from the
whole stored history on each completed export step; this is not a rolling daily export.
See [DATABASE.md](DATABASE.md) for columns, types, and view definitions.

| Relative path under `/out` | SQL query |
|---|---|
| `garmin_daily_metrics.csv` | `SELECT * FROM garmin.daily_overview ORDER BY day` |
| `garmin_activities.csv` | `SELECT * FROM garmin.activities ORDER BY start_local` |
| `garmin_strength_sets.csv` | `SELECT * FROM garmin.strength_log ORDER BY start_local, set_no` |
| `activities/garmin_activity_laps.csv` | `SELECT a.day, a.type, a.name, l.* FROM garmin.activity_laps l JOIN garmin.activities a USING (activity_id) ORDER BY a.start_local, l.lap_no` |
| `activities/garmin_activity_hr_zones.csv` | `SELECT a.day, a.type, a.name, z.* FROM garmin.activity_hr_zones z JOIN garmin.activities a USING (activity_id) ORDER BY a.start_local, z.zone` |
| `activities/garmin_activity_samples.csv` | `SELECT * FROM garmin.activity_samples ORDER BY activity_id, ts` |
| `intraday/garmin_hr.csv` | `SELECT ts, hr FROM garmin.hr_samples ORDER BY ts` |
| `intraday/garmin_stress.csv` | `SELECT ts, stress FROM garmin.stress_samples ORDER BY ts` |
| `intraday/garmin_body_battery.csv` | `SELECT ts, level FROM garmin.body_battery_samples ORDER BY ts` |
| `intraday/garmin_respiration.csv` | `SELECT ts, breaths FROM garmin.respiration_samples ORDER BY ts` |
| `intraday/garmin_hrv_night.csv` | `SELECT ts, hrv FROM garmin.hrv_samples ORDER BY ts` |
| `intraday/garmin_steps_15min.csv` | `SELECT * FROM garmin.steps_15min ORDER BY ts_start` |
| `intraday/garmin_sleep_stages.csv` | `SELECT * FROM garmin.sleep_stages ORDER BY ts_start` |

CSV encoding is UTF-8 with BOM. NULL becomes an empty cell. Aware timestamps are converted
to the configured `TZ` and written without an offset; naive timestamps retain their wall time.
Dates are written as `YYYY-MM-DD`. Units are not changed during CSV export.
