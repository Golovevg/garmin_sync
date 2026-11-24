# Справочник данных PostgreSQL

[English](../DATABASE.md) | Русский

Справочник соответствует `SCHEMA_SQL` в `collector/sync.py` и описывает текущую реализацию.
Все поля, типы и ограничения извлечены из исходной схемы. Первичный ключ подразумевает
`NOT NULL`; остальные поля допускают NULL, если явно не указано обратное. Проверки диапазонов
и разделение данных по пользователям не заданы. Единственный явно созданный дополнительный
индекс — `activities_day_idx` по `garmin.activities(day)`. PostgreSQL также создаёт индексы
первичных ключей.

## `raw.daily`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `day` | `date NOT NULL` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `endpoint` | `text NOT NULL` | Логическое имя исходного ответа в сборщике. |
| `payload` | `jsonb` | Исходный ответ метода Garmin в JSONB. |
| `fetched_at` | `timestamptz NOT NULL DEFAULT now()` | Время сохранения; при записи обновляется у всех сохранённых ответов соответствующей даты или тренировки. |

Ограничение таблицы: `PRIMARY KEY (day, endpoint)`.

## `raw.activity`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `activity_id` | `bigint NOT NULL` | Идентификатор тренировки Garmin. |
| `endpoint` | `text NOT NULL` | Логическое имя исходного ответа в сборщике. |
| `payload` | `jsonb` | Исходный ответ метода Garmin в JSONB. |
| `fetched_at` | `timestamptz NOT NULL DEFAULT now()` | Время сохранения; при записи обновляется у всех сохранённых ответов соответствующей даты или тренировки. |

Ограничение таблицы: `PRIMARY KEY (activity_id, endpoint)`.

## `garmin.sleep`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `day` | `date PRIMARY KEY` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `sleep_start` | `timestamptz` | Момент начала сна. |
| `sleep_end` | `timestamptz` | Момент окончания сна. |
| `total_s` | `integer` | Общая длительность сна, секунды. |
| `deep_s` | `integer` | Глубокий сон, секунды. |
| `light_s` | `integer` | Лёгкий сон, секунды. |
| `rem_s` | `integer` | Быстрый сон, секунды. |
| `awake_s` | `integer` | Бодрствование, секунды. |
| `score` | `smallint` | Общая оценка сна. |
| `quality` | `text` | Текстовая категория качества сна Garmin. |
| `avg_stress` | `real` | Средний стресс во сне. |
| `hr_avg` | `smallint` | Пульс во сне; при отсутствии используется restingHeartRate из ответа о сне. |
| `resp_avg` | `real` | Средняя частота дыхания во сне, вдохов/мин. |
| `spo2_avg` | `smallint` | Средняя сатурация, проценты. |
| `spo2_min` | `smallint` | Минимальная сатурация, проценты. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Время последнего обновления разобранной строки. |

## `garmin.heart`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `day` | `date PRIMARY KEY` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `rhr` | `smallint` | Пульс покоя, уд/мин. |
| `rhr_7d` | `smallint` | Средний пульс покоя за 7 дней, уд/мин. |
| `hr_min` | `smallint` | Минимальный пульс за день, уд/мин. |
| `hr_max` | `smallint` | Максимальный пульс за день, уд/мин. |
| `hrv_night` | `smallint` | Средний ночной HRV, мс. |
| `hrv_night_max5` | `smallint` | Максимальный HRV за пятиминутный ночной интервал, мс. |
| `hrv_week` | `smallint` | Средний HRV за неделю, мс. |
| `hrv_status` | `text` | Статус HRV Garmin. |
| `hrv_baseline_low` | `smallint` | Нижняя граница базового диапазона HRV, мс. |
| `hrv_baseline_high` | `smallint` | Верхняя граница базового диапазона HRV, мс. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Время последнего обновления разобранной строки. |

## `garmin.stress_energy`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `day` | `date PRIMARY KEY` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `stress_avg` | `smallint` | Средний стресс за день. |
| `stress_max` | `smallint` | Максимальный стресс за день. |
| `rest_s` | `integer` | Время отдыха по показателю стресса, секунды. |
| `low_s` | `integer` | Время низкого стресса, секунды. |
| `medium_s` | `integer` | Время среднего стресса, секунды. |
| `high_s` | `integer` | Время высокого стресса, секунды. |
| `bb_max` | `smallint` | Максимальное значение Body Battery. |
| `bb_min` | `smallint` | Минимальное значение Body Battery. |
| `bb_wake` | `smallint` | Body Battery при пробуждении. |
| `bb_charged` | `smallint` | Заряд Body Battery. |
| `bb_drained` | `smallint` | Расход Body Battery. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Время последнего обновления разобранной строки. |

## `garmin.movement`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `day` | `date PRIMARY KEY` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `steps` | `integer` | Количество шагов. |
| `step_goal` | `integer` | Суточная цель по шагам. |
| `distance_m` | `integer` | Дистанция, метры. |
| `floors_up` | `real` | Подъём, этажи. |
| `floors_down` | `real` | Спуск, этажи. |
| `calories_total` | `integer` | Общая энергия, ккал. |
| `calories_active` | `integer` | Активная энергия, ккал. |
| `calories_bmr` | `integer` | Базовая энергия, ккал. |
| `intensity_moderate_min` | `smallint` | Минуты умеренной интенсивности. |
| `intensity_vigorous_min` | `smallint` | Минуты высокой интенсивности. |
| `sedentary_s` | `integer` | Малоподвижное время, секунды. |
| `active_s` | `integer` | Активное время, секунды. |
| `highly_active_s` | `integer` | Время высокой активности, секунды. |
| `resp_waking` | `real` | Средняя частота дыхания днём, вдохов/мин. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Время последнего обновления разобранной строки. |

## `garmin.training`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `day` | `date PRIMARY KEY` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `readiness_score` | `smallint` | Оценка готовности к тренировке. |
| `readiness_level` | `text` | Категория готовности Garmin. |
| `training_status` | `text` | Текстовая оценка тренировочного статуса Garmin. |
| `load_acute` | `real` | Острая тренировочная нагрузка Garmin. |
| `load_chronic` | `real` | Хроническая тренировочная нагрузка Garmin. |
| `load_ratio` | `real` | Отношение острой нагрузки к хронической. |
| `vo2max_run` | `real` | МПК бега, мл/кг/мин. |
| `vo2max_bike` | `real` | МПК велоспорта, мл/кг/мин. |
| `fitness_age` | `real` | Фитнес-возраст, годы. |
| `endurance_score` | `smallint` | Оценка выносливости Garmin. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Время последнего обновления разобранной строки. |

## `garmin.body`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `day` | `date PRIMARY KEY` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `weight_kg` | `real` | Вес, кг; см. ограничение преобразования единиц в описании архитектуры. |
| `bmi` | `real` | Индекс массы тела. |
| `body_fat_pct` | `real` | Доля жира, проценты. |
| `muscle_kg` | `real` | Мышечная масса, кг. |
| `bone_kg` | `real` | Костная масса, кг. |
| `body_water_pct` | `real` | Доля воды, проценты. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Время последнего обновления разобранной строки. |

## `garmin.hydration`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `day` | `date PRIMARY KEY` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `intake_ml` | `integer` | Потребление воды, мл. |
| `goal_ml` | `integer` | Цель по воде, мл. |
| `sweat_loss_ml` | `integer` | Оценка потери воды с потом, мл. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Время последнего обновления разобранной строки. |

## `garmin.hr_samples`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Момент измерения. |
| `hr` | `smallint` | Пульс, уд/мин. |

## `garmin.stress_samples`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Момент измерения. |
| `stress` | `smallint` | Значение стресса. |

## `garmin.body_battery_samples`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Момент измерения. |
| `level` | `smallint` | Уровень Body Battery либо исходный числовой уровень сна, в зависимости от таблицы. |

## `garmin.respiration_samples`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Момент измерения. |
| `breaths` | `real` | Частота дыхания, вдохов/мин. |

## `garmin.hrv_samples`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `ts` | `timestamptz PRIMARY KEY` | Момент измерения. |
| `hrv` | `smallint` | Значение HRV, мс. |

## `garmin.steps_15min`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `ts_start` | `timestamptz PRIMARY KEY` | Начало интервала. |
| `ts_end` | `timestamptz` | Конец интервала. |
| `steps` | `integer` | Количество шагов. |
| `activity_level` | `text` | Основной уровень активности Garmin. |

## `garmin.sleep_stages`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `ts_start` | `timestamptz PRIMARY KEY` | Начало интервала. |
| `ts_end` | `timestamptz` | Конец интервала. |
| `stage` | `text` | Фаза сна: deep/light/rem/awake. |
| `level` | `real` | Уровень Body Battery либо исходный числовой уровень сна, в зависимости от таблицы. |

## `garmin.activities`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `activity_id` | `bigint PRIMARY KEY` | Идентификатор тренировки Garmin. |
| `day` | `date` | Календарная дата; для тренировки определяется по startTimeLocal. |
| `start_local` | `timestamp` | Местное время начала тренировки Garmin без часового пояса. |
| `start_utc` | `timestamptz` | Момент начала, интерпретируемый как UTC. |
| `type` | `text` | Ключ типа тренировки Garmin. |
| `name` | `text` | Название тренировки Garmin. |
| `duration_s` | `real` | Длительность, секунды. |
| `moving_s` | `real` | Время движения, секунды. |
| `elapsed_s` | `real` | Полное прошедшее время, секунды. |
| `distance_m` | `real` | Дистанция, метры. |
| `calories` | `real` | Энергия, ккал. |
| `avg_hr` | `smallint` | Средний пульс, уд/мин. |
| `max_hr` | `smallint` | Максимальный пульс, уд/мин. |
| `avg_speed_ms` | `real` | Средняя скорость, м/с. |
| `max_speed_ms` | `real` | Максимальная скорость, м/с. |
| `elev_gain_m` | `real` | Набор высоты, метры. |
| `elev_loss_m` | `real` | Потеря высоты, метры. |
| `avg_cadence` | `real` | Средний каденс; единицы зависят от типа тренировки и исходного поля. |
| `avg_power` | `real` | Средняя мощность, Вт. |
| `max_power` | `real` | Максимальная мощность, Вт. |
| `norm_power` | `real` | Нормализованная мощность, Вт. |
| `te_aerobic` | `real` | Аэробный тренировочный эффект. |
| `te_anaerobic` | `real` | Анаэробный тренировочный эффект. |
| `training_load` | `real` | Нагрузка тренировки. |
| `vo2max` | `real` | МПК тренировки, мл/кг/мин. |
| `steps` | `integer` | Количество шагов. |
| `total_sets` | `integer` | Заявленное число всех или активных подходов. |
| `total_reps` | `integer` | Заявленное общее число повторений. |
| `device_id` | `bigint` | Идентификатор устройства Garmin. |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Время последнего обновления разобранной строки. |

## `garmin.activity_laps`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `activity_id` | `bigint REFERENCES garmin.activities ON DELETE CASCADE` | Идентификатор тренировки Garmin. |
| `lap_no` | `smallint` | Индекс круга Garmin или номер из перечисления. |
| `start_utc` | `timestamptz` | Момент начала, интерпретируемый как UTC. |
| `duration_s` | `real` | Длительность, секунды. |
| `distance_m` | `real` | Дистанция, метры. |
| `avg_hr` | `smallint` | Средний пульс, уд/мин. |
| `max_hr` | `smallint` | Максимальный пульс, уд/мин. |
| `avg_speed_ms` | `real` | Средняя скорость, м/с. |
| `elev_gain_m` | `real` | Набор высоты, метры. |
| `calories` | `real` | Энергия, ккал. |

Ограничение таблицы: `PRIMARY KEY (activity_id, lap_no)`.

## `garmin.activity_hr_zones`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `activity_id` | `bigint REFERENCES garmin.activities ON DELETE CASCADE` | Идентификатор тренировки Garmin. |
| `zone` | `smallint` | Номер пульсовой зоны. |
| `seconds` | `real` | Время в зоне, секунды. |
| `low_bpm` | `smallint` | Нижняя граница зоны, уд/мин. |

Ограничение таблицы: `PRIMARY KEY (activity_id, zone)`.

## `garmin.strength_sets`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `activity_id` | `bigint REFERENCES garmin.activities ON DELETE CASCADE` | Идентификатор тренировки Garmin. |
| `set_no` | `smallint` | messageIndex Garmin или номер из перечисления, начиная с нуля. |
| `set_type` | `text` | Тип подхода Garmin, например ACTIVE или REST. |
| `start_utc` | `timestamptz` | Момент начала, интерпретируемый как UTC. |
| `duration_s` | `real` | Длительность, секунды. |
| `exercise` | `text` | Упражнение с максимальной вероятностью распознавания; при отсутствии имени — категория. |
| `category` | `text` | Категория выбранного упражнения. |
| `reps` | `smallint` | Количество повторений. |
| `weight_kg` | `real` | Вес, кг; см. ограничение преобразования единиц в описании архитектуры. |

Ограничение таблицы: `PRIMARY KEY (activity_id, set_no)`.

## `garmin.activity_samples`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `activity_id` | `bigint REFERENCES garmin.activities ON DELETE CASCADE` | Идентификатор тренировки Garmin. |
| `ts` | `timestamptz` | Момент измерения. |
| `hr` | `smallint` | Пульс, уд/мин. |
| `speed_ms` | `real` | Скорость измерения, м/с. |
| `cadence` | `real` | Исходный каденс; нормализация единиц не выполняется. |
| `power` | `real` | Мощность измерения, Вт. |
| `elevation_m` | `real` | Высота, метры. |
| `lat` | `double precision` | Широта. |
| `lon` | `double precision` | Долгота. |
| `distance_m` | `real` | Дистанция, метры. |

Ограничение таблицы: `PRIMARY KEY (activity_id, ts)`.

## `garmin.activity_files`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `activity_id` | `bigint PRIMARY KEY REFERENCES garmin.activities ON DELETE CASCADE` | Идентификатор тренировки Garmin. |
| `file_name` | `text` | Имя локального файла в /out/fit. |
| `bytes` | `integer` | Размер скачанного архива, байты. |
| `downloaded_at` | `timestamptz NOT NULL DEFAULT now()` | Время первоначального создания записи файла; текущий upsert его не обновляет. |

## `garmin.sync_state`

| Поле | Тип и ограничения поля | Значение / единицы |
|---|---|---|
| `key` | `text PRIMARY KEY` | Имя контрольной даты: days_done_until или activities_done_until. |
| `value` | `text NOT NULL` | Контрольная дата строкой ISO YYYY-MM-DD. |

## Связи и принадлежность данных

Таблицы `activity_laps`, `activity_hr_zones`, `strength_sets`, `activity_samples` и
`activity_files` ссылаются на `garmin.activities(activity_id)` с `ON DELETE CASCADE`.
Между исходными, суточными, внутридневными таблицами и контрольными датами внешних ключей нет.
Поля учётной записи или спортсмена нет: один экземпляр приложения рассчитан на один аккаунт Garmin.

## Представления и точные поля выгрузок

`garmin.daily_overview` берёт уникальные даты из `raw.daily`, присоединяет суточные таблицы
через LEFT JOIN и агрегаты тренировок: число `workouts`, округлённую сумму длительностей
`workout_s` и округлённую сумму калорий `workout_kcal`. Отсутствующие присоединённые данные
остаются NULL, включая число тренировок, если строки агрегата нет. Даты, встречающиеся только
в тренировках, не добавляются.

`garmin.strength_log` соединяет подходы с тренировками, включая активные подходы и отдых:
фильтра по `set_type` нет. Название тренировки выводится как `workout`.

Ниже приведены точные SQL-определения со всеми выходными полями и псевдонимами:

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
