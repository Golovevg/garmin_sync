# Данные Garmin и файлы выгрузок

[English](../ENDPOINTS_AND_EXPORTS.md) | Русский

## Суточные запросы

`fetch_day()` последовательно вызывает следующие методы с датой ISO. Доступность зависит от
аккаунта Garmin, устройства, API и установленной версии `garminconnect`. Это перечень
реализованных запросов, а не гарантия получения всех категорий данных Garmin.

| Имя исходного ответа | Метод библиотеки |
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

## Запросы тренировок

| Имя в raw.activity | Источник / метод |
|---|---|
| `list` | Элемент результата `get_activities_by_date(start, end)` |
| `summary` | `get_activity(activity_id)` |
| `splits` | `get_activity_splits(activity_id)` |
| `hr_zones` | `get_activity_hr_in_timezones(activity_id)` |
| `exercise_sets` | `get_activity_exercise_sets(activity_id)` |
| `details` | `get_activity_details(activity_id)` |

Подходы запрашиваются для `strength_training`, `hiit`, `indoor_cardio`, `fitness_equipment`,
а также если элемент списка содержит число всех или активных подходов. Исходные файлы
скачиваются отдельно через `download_activity` при `DOWNLOAD_FIT=1`.
Двоичные файлы не сохраняются в `raw.activity`.

## SQL-запросы выгрузок

Заголовок CSV берётся из результата SQL. При каждой выгрузке заново создаются файлы за всю
сохранённую историю, а не только за последние дни. Поля, типы и представления описаны
в [справочнике базы](DATABASE.md).

| Путь относительно `/out` | SQL-запрос |
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

Кодировка CSV — UTF-8 с BOM. NULL превращается в пустую ячейку. Время с часовым поясом
переводится в настроенный `TZ` и записывается без смещения; время без часового пояса
сохраняется как местное время. Формат даты — `YYYY-MM-DD`. Единицы измерений при выгрузке
не преобразуются.
