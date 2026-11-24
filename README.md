# Garmin → PostgreSQL → Google Drive (Docker на Mac mini)

Сборщик дважды в сутки (09:00 и 22:00 МСК) забирает из Garmin Connect **все** данные:
суточные показатели, данные внутри дня и тренировки с подходами и FIT-файлами.
Пишет их в PostgreSQL, выгружает CSV и FIT в Google Drive и делает бэкап базы.

## Как устроена база

| Схема | Что лежит | Зачем |
|---|---|---|
| `raw` | Ответы Garmin как есть (jsonb): `raw.daily` — по дням, `raw.activity` — по тренировкам | Источник истины. Из него пересобирается всё остальное без повторных запросов к Garmin (`--reparse`) |
| `garmin` | Разобранные таблицы и представления | Для анализа и выгрузки |
| `legacy` | Таблицы версии 1 (`daily_metrics`, `sync_state`) | Переносятся сюда автоматически; удалить после проверки |

**По дням** — одна строка на день, ключ `day`:

| Таблица | Показатели |
|---|---|
| `garmin.sleep` | начало и конец сна, фазы (глубокий, лёгкий, REM, бодрствование), оценка, стресс и пульс во сне, дыхание, SpO2 |
| `garmin.heart` | пульс покоя (день и 7 дней), мин/макс пульс, HRV за ночь, за 7 дней, статус и коридор нормы |
| `garmin.stress_energy` | стресс (средний, макс, время по уровням), Body Battery (макс, мин, при пробуждении, заряд, расход) |
| `garmin.movement` | шаги и цель, дистанция, этажи, калории (всего, активные, базовые), минуты интенсивности, время активности, дыхание днём |
| `garmin.training` | готовность к тренировке, тренировочный статус, острая и хроническая нагрузка, МПК бег/вело, фитнес-возраст, выносливость |
| `garmin.body` | вес, ИМТ, жир, мышцы, кости, вода |
| `garmin.hydration` | выпито воды, цель, потеря с потом |

**Внутри дня** — ключ «время»: `hr_samples` (пульс), `stress_samples`, `body_battery_samples`,
`respiration_samples`, `hrv_samples` (HRV ночью), `steps_15min`, `sleep_stages`.

**Тренировки** — ключ `activity_id`:

| Таблица | Что |
|---|---|
| `garmin.activities` | одна строка на тренировку: тип, время, длительность, дистанция, пульс, темп, каденс, мощность, набор высоты, эффект, нагрузка |
| `garmin.activity_laps` | круги и отрезки |
| `garmin.activity_hr_zones` | время в пульсовых зонах |
| `garmin.strength_sets` | подходы силовых: упражнение, повторы, вес (кг), отдых |
| `garmin.activity_samples` | посекундные данные: пульс, скорость, каденс, мощность, высота, координаты |
| `garmin.activity_files` | скачанные FIT-файлы |

**Представления для выгрузки:** `garmin.daily_overview` (все суточные таблицы в одну строку на день
плюс число тренировок), `garmin.strength_log` (подходы с датой и названием тренировки).

Связи: дочерние таблицы тренировок ссылаются на `garmin.activities` (`ON DELETE CASCADE`).
Время хранится в `timestamptz`, в CSV выводится по Москве.

## Что попадает в Google Drive (папка `RCLONE_REMOTE`)

```
garmin_daily_metrics.csv        ← garmin.daily_overview
garmin_activities.csv
garmin_strength_sets.csv        ← garmin.strength_log
activities/  garmin_activity_laps.csv, garmin_activity_hr_zones.csv, garmin_activity_samples.csv
intraday/    garmin_hr.csv, garmin_stress.csv, garmin_body_battery.csv, garmin_respiration.csv,
             garmin_hrv_night.csv, garmin_steps_15min.csv, garmin_sleep_stages.csv
fit/         исходные файлы тренировок с часов (zip с FIT)
backups/     pg_dump за последние 14 дней
```

## Как идёт загрузка

- Первый запуск версии 2 заново проходит всю историю: с самого раннего дня в базе (или `BACKFILL_FROM`).
  Около 17 запросов на день и до 6 на тренировку, с паузами. За 90 дней — порядка 20–40 минут.
- Дальше каждый проход перечитывает последние `RESYNC_DAYS` дней и тренировки за эти дни:
  Garmin досинхронизирует с опозданием, а веса в подходах можно поправить задним числом.
- Ошибка 429 (слишком много запросов): пауза 10 минут, затем проход прерывается
  и следующий продолжает с того же места.
- Если какого-то показателя нет (например, нет весов), это не ошибка: в журнале одна строка, поле пустое.

## Команды

```bash
docker compose up -d --build                               # запуск / обновление
docker compose run --rm collector python sync.py --login   # вход в Garmin (email, пароль, код MFA)
docker compose run --rm collector python sync.py --once    # один проход вручную
docker compose run --rm collector python sync.py --reparse # пересобрать таблицы из raw.*, без Garmin
tail -f logs/sync.log                                      # журнал
```

## Доступ к базе с Mac mini

`psql postgresql://garmin:<PG_PASSWORD из .env>@127.0.0.1:5432/garmin`

## Секреты — никуда не выкладывать

`.env`, `tokens/` (токены Garmin), `rclone/` (доступ к Google Drive). Всё это в `.gitignore`.
