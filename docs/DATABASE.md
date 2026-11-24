# PostgreSQL data dictionary

This catalog follows `SCHEMA_SQL` in `collector/sync.py`. It documents the current implementation, not planned behavior.

All columns, types, inline constraints, and table primary keys below are extracted from the source schema. A primary key implies `NOT NULL`; otherwise columns are nullable unless stated. No range checks or multi-user isolation are defined. The only explicit secondary index is `activities_day_idx` on `garmin.activities(day)`. PostgreSQL also creates indexes for primary keys.

## `raw.daily`

One response per calendar day and endpoint.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `day` | `date NOT NULL` | Calendar date; activity dates come from startTimeLocal. |
| `endpoint` | `text NOT NULL` | Logical response name used by the collector. |
| `payload` | `jsonb` | Original endpoint response as JSONB. |
| `fetched_at` | `timestamptz NOT NULL DEFAULT now()` | Local fetch timestamp; refreshed for all stored endpoints for this day/activity on save. |

Table constraint: `PRIMARY KEY (day, endpoint)`.

## `raw.activity`

One response per activity and endpoint.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `activity_id` | `bigint NOT NULL` | Garmin activity identifier. |
| `endpoint` | `text NOT NULL` | Logical response name used by the collector. |
| `payload` | `jsonb` | Original endpoint response as JSONB. |
| `fetched_at` | `timestamptz NOT NULL DEFAULT now()` | Local fetch timestamp; refreshed for all stored endpoints for this day/activity on save. |

Table constraint: `PRIMARY KEY (activity_id, endpoint)`.

## `garmin.sleep`

Daily sleep summary.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `day` | `date PRIMARY KEY` | Calendar date; activity dates come from startTimeLocal. |
| `sleep_start` | `timestamptz` | Sleep start instant. |
| `sleep_end` | `timestamptz` | Sleep end instant. |
| `total_s` | `integer` | Total sleep duration, seconds. |
| `deep_s` | `integer` | Deep sleep duration, seconds. |
| `light_s` | `integer` | Light sleep duration, seconds. |
| `rem_s` | `integer` | REM sleep duration, seconds. |
| `awake_s` | `integer` | Awake duration, seconds. |
| `score` | `smallint` | Overall sleep score. |
| `quality` | `text` | Sleep quality qualifier from Garmin. |
| `avg_stress` | `real` | Average sleep stress. |
| `hr_avg` | `smallint` | Sleep heart rate; falls back to the sleep response restingHeartRate field. |
| `resp_avg` | `real` | Average sleep respiration, breaths/min. |
| `spo2_avg` | `smallint` | Average oxygen saturation, percent. |
| `spo2_min` | `smallint` | Lowest oxygen saturation, percent. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Local time of the latest normalized-row update. |

## `garmin.heart`

Daily heart rate and HRV.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `day` | `date PRIMARY KEY` | Calendar date; activity dates come from startTimeLocal. |
| `rhr` | `smallint` | Resting heart rate, bpm. |
| `rhr_7d` | `smallint` | Seven-day average resting heart rate, bpm. |
| `hr_min` | `smallint` | Minimum daily heart rate, bpm. |
| `hr_max` | `smallint` | Maximum daily heart rate, bpm. |
| `hrv_night` | `smallint` | Average nightly HRV, ms. |
| `hrv_night_max5` | `smallint` | Highest five-minute nightly HRV, ms. |
| `hrv_week` | `smallint` | Weekly average HRV, ms. |
| `hrv_status` | `text` | Garmin HRV status. |
| `hrv_baseline_low` | `smallint` | Lower HRV baseline boundary, ms. |
| `hrv_baseline_high` | `smallint` | Upper HRV baseline boundary, ms. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Local time of the latest normalized-row update. |

## `garmin.stress_energy`

Daily stress and Body Battery.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `day` | `date PRIMARY KEY` | Calendar date; activity dates come from startTimeLocal. |
| `stress_avg` | `smallint` | Average daily stress. |
| `stress_max` | `smallint` | Maximum daily stress. |
| `rest_s` | `integer` | Rest stress duration, seconds. |
| `low_s` | `integer` | Low stress duration, seconds. |
| `medium_s` | `integer` | Medium stress duration, seconds. |
| `high_s` | `integer` | High stress duration, seconds. |
| `bb_max` | `smallint` | Highest Body Battery value. |
| `bb_min` | `smallint` | Lowest Body Battery value. |
| `bb_wake` | `smallint` | Body Battery at wake-up. |
| `bb_charged` | `smallint` | Body Battery charged value. |
| `bb_drained` | `smallint` | Body Battery drained value. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Local time of the latest normalized-row update. |

## `garmin.movement`

Daily movement and energy.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `day` | `date PRIMARY KEY` | Calendar date; activity dates come from startTimeLocal. |
| `steps` | `integer` | Step count. |
| `step_goal` | `integer` | Daily step goal. |
| `distance_m` | `integer` | Distance, meters. |
| `floors_up` | `real` | Floors ascended. |
| `floors_down` | `real` | Floors descended. |
| `calories_total` | `integer` | Total energy, kcal. |
| `calories_active` | `integer` | Active energy, kcal. |
| `calories_bmr` | `integer` | Basal energy, kcal. |
| `intensity_moderate_min` | `smallint` | Moderate intensity minutes. |
| `intensity_vigorous_min` | `smallint` | Vigorous intensity minutes. |
| `sedentary_s` | `integer` | Sedentary time, seconds. |
| `active_s` | `integer` | Active time, seconds. |
| `highly_active_s` | `integer` | Highly active time, seconds. |
| `resp_waking` | `real` | Average waking respiration, breaths/min. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Local time of the latest normalized-row update. |

## `garmin.training`

Daily training status and fitness metrics.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `day` | `date PRIMARY KEY` | Calendar date; activity dates come from startTimeLocal. |
| `readiness_score` | `smallint` | Training readiness score. |
| `readiness_level` | `text` | Garmin readiness level. |
| `training_status` | `text` | Garmin training status feedback phrase. |
| `load_acute` | `real` | Garmin acute training load. |
| `load_chronic` | `real` | Garmin chronic training load. |
| `load_ratio` | `real` | Acute/chronic workload ratio. |
| `vo2max_run` | `real` | Running VO2 max, mL/kg/min. |
| `vo2max_bike` | `real` | Cycling VO2 max, mL/kg/min. |
| `fitness_age` | `real` | Fitness age, years. |
| `endurance_score` | `smallint` | Garmin endurance score. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Local time of the latest normalized-row update. |

## `garmin.body`

Daily body composition.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `day` | `date PRIMARY KEY` | Calendar date; activity dates come from startTimeLocal. |
| `weight_kg` | `real` | Weight, kg; see conversion caveat in architecture documentation. |
| `bmi` | `real` | Body mass index. |
| `body_fat_pct` | `real` | Body fat percentage. |
| `muscle_kg` | `real` | Muscle mass, kg. |
| `bone_kg` | `real` | Bone mass, kg. |
| `body_water_pct` | `real` | Body water percentage. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Local time of the latest normalized-row update. |

## `garmin.hydration`

Daily hydration.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `day` | `date PRIMARY KEY` | Calendar date; activity dates come from startTimeLocal. |
| `intake_ml` | `integer` | Water intake, mL. |
| `goal_ml` | `integer` | Hydration goal, mL. |
| `sweat_loss_ml` | `integer` | Estimated sweat loss, mL. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Local time of the latest normalized-row update. |

## `garmin.hr_samples`

Intraday heart rate.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Sample timestamp. |
| `hr` | `smallint` | Heart rate, bpm. |

## `garmin.stress_samples`

Intraday stress.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Sample timestamp. |
| `stress` | `smallint` | Stress sample value. |

## `garmin.body_battery_samples`

Intraday Body Battery.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Sample timestamp. |
| `level` | `smallint` | Body Battery level or raw sleep activity level, depending on table. |

## `garmin.respiration_samples`

Intraday respiration.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Sample timestamp. |
| `breaths` | `real` | Respiration, breaths/min. |

## `garmin.hrv_samples`

Nightly HRV samples.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Sample timestamp. |
| `hrv` | `smallint` | HRV sample value, ms. |

## `garmin.steps_15min`

Step-count intervals.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `ts_start` | `timestamptz PRIMARY KEY` | Interval start instant. |
| `ts_end` | `timestamptz` | Interval end instant. |
| `steps` | `integer` | Step count. |
| `activity_level` | `text` | Garmin primary activity level. |

## `garmin.sleep_stages`

Sleep-stage intervals.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `ts_start` | `timestamptz PRIMARY KEY` | Interval start instant. |
| `ts_end` | `timestamptz` | Interval end instant. |
| `stage` | `text` | Mapped sleep stage: deep/light/rem/awake. |
| `level` | `real` | Body Battery level or raw sleep activity level, depending on table. |

## `garmin.activities`

One summary per Garmin activity.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `activity_id` | `bigint PRIMARY KEY` | Garmin activity identifier. |
| `day` | `date` | Calendar date; activity dates come from startTimeLocal. |
| `start_local` | `timestamp` | Garmin activity-local start time, stored without a time zone. |
| `start_utc` | `timestamptz` | Start instant interpreted as UTC. |
| `type` | `text` | Garmin activity type key. |
| `name` | `text` | Garmin activity name. |
| `duration_s` | `real` | Duration, seconds. |
| `moving_s` | `real` | Moving duration, seconds. |
| `elapsed_s` | `real` | Elapsed duration, seconds. |
| `distance_m` | `real` | Distance, meters. |
| `calories` | `real` | Energy, kcal. |
| `avg_hr` | `smallint` | Average heart rate, bpm. |
| `max_hr` | `smallint` | Maximum heart rate, bpm. |
| `avg_speed_ms` | `real` | Average speed, meters/second. |
| `max_speed_ms` | `real` | Maximum speed, meters/second. |
| `elev_gain_m` | `real` | Elevation gain, meters. |
| `elev_loss_m` | `real` | Elevation loss, meters. |
| `avg_cadence` | `real` | Average cadence; unit depends on activity and source field. |
| `avg_power` | `real` | Average power, watts. |
| `max_power` | `real` | Maximum power, watts. |
| `norm_power` | `real` | Normalized power, watts. |
| `te_aerobic` | `real` | Aerobic training effect. |
| `te_anaerobic` | `real` | Anaerobic training effect. |
| `training_load` | `real` | Activity training load. |
| `vo2max` | `real` | Activity VO2 max, mL/kg/min. |
| `steps` | `integer` | Step count. |
| `total_sets` | `integer` | Reported total/active set count. |
| `total_reps` | `integer` | Reported total repetitions. |
| `device_id` | `bigint` | Garmin device identifier. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Local time of the latest normalized-row update. |

## `garmin.activity_laps`

Activity laps.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `activity_id` | `bigint REFERENCES garmin.activities ON DELETE CASCADE` | Garmin activity identifier. |
| `lap_no` | `smallint` | Garmin lap index, or enumeration fallback. |
| `start_utc` | `timestamptz` | Start instant interpreted as UTC. |
| `duration_s` | `real` | Duration, seconds. |
| `distance_m` | `real` | Distance, meters. |
| `avg_hr` | `smallint` | Average heart rate, bpm. |
| `max_hr` | `smallint` | Maximum heart rate, bpm. |
| `avg_speed_ms` | `real` | Average speed, meters/second. |
| `elev_gain_m` | `real` | Elevation gain, meters. |
| `calories` | `real` | Energy, kcal. |

Table constraint: `PRIMARY KEY (activity_id, lap_no)`.

## `garmin.activity_hr_zones`

Activity heart rate zone durations.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `activity_id` | `bigint REFERENCES garmin.activities ON DELETE CASCADE` | Garmin activity identifier. |
| `zone` | `smallint` | Heart rate zone number. |
| `seconds` | `real` | Time in the zone, seconds. |
| `low_bpm` | `smallint` | Lower zone boundary, bpm. |

Table constraint: `PRIMARY KEY (activity_id, zone)`.

## `garmin.strength_sets`

Active and rest sets.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `activity_id` | `bigint REFERENCES garmin.activities ON DELETE CASCADE` | Garmin activity identifier. |
| `set_no` | `smallint` | Garmin message index, or zero-based enumeration fallback. |
| `set_type` | `text` | Garmin set type, such as ACTIVE or REST. |
| `start_utc` | `timestamptz` | Start instant interpreted as UTC. |
| `duration_s` | `real` | Duration, seconds. |
| `exercise` | `text` | Highest-probability exercise name, with category fallback. |
| `category` | `text` | Category of the selected exercise. |
| `reps` | `smallint` | Repetition count. |
| `weight_kg` | `real` | Weight, kg; see conversion caveat in architecture documentation. |

Table constraint: `PRIMARY KEY (activity_id, set_no)`.

## `garmin.activity_samples`

Activity detail samples at the resolution supplied by Garmin.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `activity_id` | `bigint REFERENCES garmin.activities ON DELETE CASCADE` | Garmin activity identifier. |
| `ts` | `timestamptz` | Sample timestamp. |
| `hr` | `smallint` | Heart rate, bpm. |
| `speed_ms` | `real` | Sample speed, meters/second. |
| `cadence` | `real` | Source cadence sample; no cadence-unit normalization is applied. |
| `power` | `real` | Power sample, watts. |
| `elevation_m` | `real` | Elevation, meters. |
| `lat` | `double precision` | Latitude. |
| `lon` | `double precision` | Longitude. |
| `distance_m` | `real` | Distance, meters. |

Table constraint: `PRIMARY KEY (activity_id, ts)`.

## `garmin.activity_files`

Download manifest; binary data is stored on disk.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `activity_id` | `bigint PRIMARY KEY REFERENCES garmin.activities ON DELETE CASCADE` | Garmin activity identifier. |
| `file_name` | `text` | Local filename under /out/fit. |
| `bytes` | `integer` | Downloaded archive size, bytes. |
| `downloaded_at` | `timestamptz NOT NULL DEFAULT now()` | Timestamp set on initial file-row insertion; not refreshed by the current upsert. |

## `garmin.sync_state`

Independent daily and activity checkpoints.

| Field | Type and inline constraints | Meaning / unit |
|---|---|---|
| `key` | `text PRIMARY KEY` | Checkpoint name: days_done_until or activities_done_until. |
| `value` | `text NOT NULL` | Checkpoint date as an ISO YYYY-MM-DD string. |

## Relationships and ownership

The five child tables `activity_laps`, `activity_hr_zones`, `strength_sets`, `activity_samples`,
and `activity_files` reference `garmin.activities(activity_id)` with `ON DELETE CASCADE`.
The raw tables, daily tables, intraday tables, and checkpoints have no foreign keys to one another.
There is no athlete/account key: one deployment is designed for one Garmin account.

## Views and exact exported column mappings

`garmin.daily_overview` starts from distinct dates in `raw.daily` and left-joins each daily table.
It also joins activity aggregates by day: count as `workouts`, rounded summed duration as `workout_s`,
and rounded summed calories as `workout_kcal`. Missing joined data remains NULL, including the
activity count when no aggregate row exists. Dates occurring only in activities are not added.

`garmin.strength_log` joins sets to activities. It includes both active and rest sets; it does not
filter `set_type`. The activity name is exposed as `workout`.

Exact definitions below enumerate every output field and alias:

```sql
DROP VIEW IF EXISTS garmin.daily_overview;
CREATE VIEW garmin.daily_overview AS
SELECT d.day,
       h.rhr, h.rhr_7d, h.hr_min, h.hr_max,
       h.hrv_night, h.hrv_night_max5, h.hrv_week, h.hrv_status, h.hrv_baseline_low, h.hrv_baseline_high,
       s.sleep_start, s.sleep_end, s.total_s AS sleep_total_s, s.deep_s AS sleep_deep_s,
       s.light_s AS sleep_light_s, s.rem_s AS sleep_rem_s, s.awake_s AS sleep_awake_s,
       s.score AS sleep_score, s.quality AS sleep_quality, s.avg_stress AS sleep_avg_stress,
       s.hr_avg AS sleep_hr_avg, s.resp_avg AS sleep_resp_avg, s.spo2_avg, s.spo2_min,
       e.stress_avg, e.stress_max, e.rest_s AS stress_rest_s, e.low_s AS stress_low_s,
       e.medium_s AS stress_medium_s, e.high_s AS stress_high_s,
       e.bb_max, e.bb_min, e.bb_wake, e.bb_charged, e.bb_drained,
       m.steps, m.step_goal, m.distance_m, m.floors_up, m.floors_down,
       m.calories_total, m.calories_active, m.calories_bmr,
       m.intensity_moderate_min, m.intensity_vigorous_min,
       m.sedentary_s, m.active_s, m.highly_active_s, m.resp_waking,
       t.readiness_score, t.readiness_level, t.training_status, t.load_acute, t.load_chronic, t.load_ratio,
       t.vo2max_run, t.vo2max_bike, t.fitness_age, t.endurance_score,
       b.weight_kg, b.bmi, b.body_fat_pct, b.muscle_kg, b.bone_kg, b.body_water_pct,
       hy.intake_ml AS water_intake_ml, hy.goal_ml AS water_goal_ml, hy.sweat_loss_ml,
       w.workouts, w.workout_s, w.workout_kcal
FROM (SELECT DISTINCT day FROM raw.daily) d
LEFT JOIN garmin.heart         h  USING (day)
LEFT JOIN garmin.sleep         s  USING (day)
LEFT JOIN garmin.stress_energy e  USING (day)
LEFT JOIN garmin.movement      m  USING (day)
LEFT JOIN garmin.training      t  USING (day)
LEFT JOIN garmin.body          b  USING (day)
LEFT JOIN garmin.hydration     hy USING (day)
LEFT JOIN (SELECT day, count(*) AS workouts, round(sum(duration_s)) AS workout_s,
                  round(sum(calories)) AS workout_kcal
           FROM garmin.activities GROUP BY day) w USING (day);

DROP VIEW IF EXISTS garmin.strength_log;
CREATE VIEW garmin.strength_log AS
SELECT a.day, a.start_local, a.name AS workout, s.set_no, s.set_type, s.exercise, s.category,
       s.reps, s.weight_kg, s.duration_s, s.start_utc, s.activity_id
FROM garmin.strength_sets s
JOIN garmin.activities a USING (activity_id);
```
