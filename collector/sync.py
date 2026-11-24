#!/usr/bin/env python3
"""
Garmin Connect -> PostgreSQL -> CSV и FIT-файлы в Google Drive.   Версия 2: выгрузка «всего».

Режимы:
    python sync.py            # служба: проход по расписанию RUN_TIMES (по умолчанию 09:00 и 22:00)
    python sync.py --once     # один проход и выход
    python sync.py --login    # первый вход: email, пароль, код MFA (интерактивно)
    python sync.py --reparse  # пересобрать таблицы garmin.* из сырых ответов raw.* (без запросов к Garmin)

Устройство базы:
    raw.*      — ответы Garmin как есть (jsonb). Источник истины: из него можно пересобрать всё остальное.
    garmin.*   — разобранные таблицы: по дням, внутри дня, тренировки; плюс представления для выгрузки.
    legacy.*   — таблицы версии 1 (переносятся сюда автоматически, можно удалить после проверки).

Инкрементальная загрузка:
    - первый запуск версии 2 заново проходит всю историю (с самого раннего дня в базе или BACKFILL_FROM),
      потому что раньше собиралась только часть показателей;
    - дальше каждый проход берёт дни и тренировки от «последний загруженный − RESYNC_DAYS» до сегодня
      и перезаписывает их, потому что Garmin досинхронизирует данные с опозданием
      (и потому что веса в подходах можно поправить в Garmin Connect задним числом).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

TZ = ZoneInfo(os.environ.get("TZ", "Europe/Moscow"))
UTC = dt.timezone.utc
PG_DSN = os.environ.get("PG_DSN", "")
TOKENS = "/tokens"
OUT = Path(os.environ.get("OUT_DIR", "/out"))
DUMPS = Path(os.environ.get("DUMPS_DIR", "/dumps"))
LOG = Path(os.environ.get("LOG_FILE", "/logs/sync.log"))
RUN_TIMES = [t.strip() for t in os.environ.get("RUN_TIMES", "09:00,22:00").split(",") if t.strip()]
BACKFILL_FROM = os.environ.get("BACKFILL_FROM", "").strip()
BACKFILL_DAYS_DEFAULT = int(os.environ.get("BACKFILL_DAYS_DEFAULT", "90"))
RESYNC_DAYS = int(os.environ.get("RESYNC_DAYS", "3"))
RCLONE_REMOTE = os.environ.get("RCLONE_REMOTE", "").strip()
KEEP_DUMPS = int(os.environ.get("KEEP_DUMPS", "14"))
DOWNLOAD_FIT = os.environ.get("DOWNLOAD_FIT", "1") == "1"

PAUSE_CALL = 0.4        # секунды между запросами — чтобы не упереться в лимиты Garmin
PAUSE_DAY = 1.5
PAUSE_ACTIVITY = 1.0
RATE_LIMIT_WAIT = 600


# =====================================================================
# служебное
# =====================================================================

def now() -> dt.datetime:
    return dt.datetime.now(TZ)


def log(msg: str) -> None:
    line = f"{now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def dig(obj: Any, *path: Any) -> Any:
    """Значение по точному пути: dig(x, "a", 0, "b")."""
    for p in path:
        if isinstance(obj, dict):
            obj = obj.get(p)
        elif isinstance(obj, list) and isinstance(p, int) and -len(obj) <= p < len(obj):
            obj = obj[p]
        else:
            return None
        if obj is None:
            return None
    return obj


def find(obj: Any, *keys: str) -> Any:
    """Первое значение по любому из ключей, ищет рекурсивно. Ноль — тоже значение."""
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if v is not None and v != "":
                return v
        for v in obj.values():
            r = find(v, *keys)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find(v, *keys)
            if r is not None:
                return r
    return None


def first(*vals: Any) -> Any:
    return next((v for v in vals if v is not None and v != ""), None)


def num(v: Any, digits: int = 1) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        return round(float(v), digits)
    except (TypeError, ValueError):
        return None


def to_int(v: Any) -> int | None:
    n = num(v, 0)
    return int(n) if n is not None else None


def grams_to_kg(v: Any) -> float | None:
    n = num(v, 3)
    return round(n / 1000, 2) if n is not None else None


def set_weight_kg(v: Any) -> float | None:
    """Вес в подходе. Garmin отдаёт граммы; на случай килограммов — значения меньше 1000 оставляем как есть."""
    n = num(v, 3)
    if n is None:
        return None
    return round(n / 1000, 2) if abs(n) >= 1000 else round(n, 2)


def ms_to_ts(ms: Any) -> dt.datetime | None:
    n = num(ms, 0)
    if n is None or n <= 0:
        return None
    return dt.datetime.fromtimestamp(n / 1000, tz=UTC)


def parse_dt(s: Any) -> dt.datetime | None:
    """'2026-11-13T15:30:00.0' / '2026-11-13 15:30:00' -> datetime без часового пояса."""
    if not isinstance(s, str) or not s:
        return None
    s = s.strip().replace("T", " ")
    if "." in s:
        s = s.split(".")[0]
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def gmt_to_ts(s: Any) -> dt.datetime | None:
    d = parse_dt(s)
    return d.replace(tzinfo=UTC) if d else None


def as_date(v: Any) -> dt.date | None:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)[:10])


def as_json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


class RateLimited(Exception):
    pass


# =====================================================================
# схема базы
# =====================================================================

SCHEMA_SQL = r"""
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS garmin;

-- перенос таблиц версии 1
DO $$
BEGIN
    IF to_regclass('public.raw_daily') IS NOT NULL AND to_regclass('raw.daily') IS NULL THEN
        ALTER TABLE public.raw_daily SET SCHEMA raw;
        ALTER TABLE raw.raw_daily RENAME TO daily;
    END IF;
    IF to_regclass('public.daily_metrics') IS NOT NULL THEN
        CREATE SCHEMA IF NOT EXISTS legacy;
        ALTER TABLE public.daily_metrics SET SCHEMA legacy;
    END IF;
    IF to_regclass('public.sync_state') IS NOT NULL THEN
        CREATE SCHEMA IF NOT EXISTS legacy;
        ALTER TABLE public.sync_state SET SCHEMA legacy;
    END IF;
END $$;

-- ---------- сырые ответы Garmin ----------
CREATE TABLE IF NOT EXISTS raw.daily (
    day        date        NOT NULL,
    endpoint   text        NOT NULL,
    payload    jsonb,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (day, endpoint)
);
CREATE TABLE IF NOT EXISTS raw.activity (
    activity_id bigint      NOT NULL,
    endpoint    text        NOT NULL,
    payload     jsonb,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (activity_id, endpoint)
);

-- ---------- по дням: одна строка на день в каждой таблице ----------
CREATE TABLE IF NOT EXISTS garmin.sleep (
    day         date PRIMARY KEY,
    sleep_start timestamptz,
    sleep_end   timestamptz,
    total_s     integer,          -- сон всего, с
    deep_s      integer,
    light_s     integer,
    rem_s       integer,
    awake_s     integer,
    score       smallint,         -- оценка сна 0–100
    quality     text,             -- EXCELLENT / GOOD / FAIR / POOR
    avg_stress  real,
    hr_avg      smallint,
    resp_avg    real,             -- дыхание во сне, вдохов/мин
    spo2_avg    smallint,
    spo2_min    smallint,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS garmin.heart (
    day               date PRIMARY KEY,
    rhr               smallint,   -- пульс покоя
    rhr_7d            smallint,   -- пульс покоя, среднее за 7 дней
    hr_min            smallint,
    hr_max            smallint,
    hrv_night         smallint,   -- HRV за ночь, мс
    hrv_night_max5    smallint,   -- лучшие 5 минут ночи
    hrv_week          smallint,   -- HRV, среднее за 7 дней
    hrv_status        text,       -- BALANCED / UNBALANCED / LOW / POOR
    hrv_baseline_low  smallint,
    hrv_baseline_high smallint,
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS garmin.stress_energy (
    day        date PRIMARY KEY,
    stress_avg smallint,
    stress_max smallint,
    rest_s     integer,           -- время в покое, с
    low_s      integer,
    medium_s   integer,
    high_s     integer,
    bb_max     smallint,          -- Body Battery
    bb_min     smallint,
    bb_wake    smallint,          -- при пробуждении
    bb_charged smallint,
    bb_drained smallint,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS garmin.movement (
    day                    date PRIMARY KEY,
    steps                  integer,
    step_goal              integer,
    distance_m             integer,
    floors_up              real,
    floors_down            real,
    calories_total         integer,
    calories_active        integer,
    calories_bmr           integer,
    intensity_moderate_min smallint,
    intensity_vigorous_min smallint,
    sedentary_s            integer,
    active_s               integer,
    highly_active_s        integer,
    resp_waking            real,  -- дыхание днём, вдохов/мин
    updated_at             timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS garmin.training (
    day             date PRIMARY KEY,
    readiness_score smallint,     -- готовность к тренировке 0–100
    readiness_level text,
    training_status text,
    load_acute      real,         -- острая нагрузка (7 дней)
    load_chronic    real,         -- хроническая нагрузка (28 дней)
    load_ratio      real,
    vo2max_run      real,
    vo2max_bike     real,
    fitness_age     real,
    endurance_score smallint,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS garmin.body (
    day            date PRIMARY KEY,
    weight_kg      real,
    bmi            real,
    body_fat_pct   real,
    muscle_kg      real,
    bone_kg        real,
    body_water_pct real,
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS garmin.hydration (
    day           date PRIMARY KEY,
    intake_ml     integer,
    goal_ml       integer,
    sweat_loss_ml integer,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- ---------- внутри дня ----------
CREATE TABLE IF NOT EXISTS garmin.hr_samples           (ts timestamptz PRIMARY KEY, hr smallint);
CREATE TABLE IF NOT EXISTS garmin.stress_samples       (ts timestamptz PRIMARY KEY, stress smallint);
CREATE TABLE IF NOT EXISTS garmin.body_battery_samples (ts timestamptz PRIMARY KEY, level smallint);
CREATE TABLE IF NOT EXISTS garmin.respiration_samples  (ts timestamptz PRIMARY KEY, breaths real);
CREATE TABLE IF NOT EXISTS garmin.hrv_samples          (ts timestamptz PRIMARY KEY, hrv smallint);
CREATE TABLE IF NOT EXISTS garmin.steps_15min (
    ts_start       timestamptz PRIMARY KEY,
    ts_end         timestamptz,
    steps          integer,
    activity_level text
);
CREATE TABLE IF NOT EXISTS garmin.sleep_stages (
    ts_start timestamptz PRIMARY KEY,
    ts_end   timestamptz,
    stage    text,                -- deep / light / rem / awake
    level    real
);

-- ---------- тренировки ----------
CREATE TABLE IF NOT EXISTS garmin.activities (
    activity_id   bigint PRIMARY KEY,
    day           date,
    start_local   timestamp,
    start_utc     timestamptz,
    type          text,           -- running, cycling, strength_training, ...
    name          text,
    duration_s    real,
    moving_s      real,
    elapsed_s     real,
    distance_m    real,
    calories      real,
    avg_hr        smallint,
    max_hr        smallint,
    avg_speed_ms  real,
    max_speed_ms  real,
    elev_gain_m   real,
    elev_loss_m   real,
    avg_cadence   real,
    avg_power     real,
    max_power     real,
    norm_power    real,
    te_aerobic    real,           -- аэробный эффект
    te_anaerobic  real,
    training_load real,
    vo2max        real,
    steps         integer,
    total_sets    integer,
    total_reps    integer,
    device_id     bigint,
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS activities_day_idx ON garmin.activities (day);

CREATE TABLE IF NOT EXISTS garmin.activity_laps (
    activity_id  bigint REFERENCES garmin.activities ON DELETE CASCADE,
    lap_no       smallint,
    start_utc    timestamptz,
    duration_s   real,
    distance_m   real,
    avg_hr       smallint,
    max_hr       smallint,
    avg_speed_ms real,
    elev_gain_m  real,
    calories     real,
    PRIMARY KEY (activity_id, lap_no)
);
CREATE TABLE IF NOT EXISTS garmin.activity_hr_zones (
    activity_id bigint REFERENCES garmin.activities ON DELETE CASCADE,
    zone        smallint,
    seconds     real,
    low_bpm     smallint,
    PRIMARY KEY (activity_id, zone)
);
CREATE TABLE IF NOT EXISTS garmin.strength_sets (
    activity_id bigint REFERENCES garmin.activities ON DELETE CASCADE,
    set_no      smallint,
    set_type    text,             -- ACTIVE / REST
    start_utc   timestamptz,
    duration_s  real,
    exercise    text,
    category    text,
    reps        smallint,
    weight_kg   real,
    PRIMARY KEY (activity_id, set_no)
);
CREATE TABLE IF NOT EXISTS garmin.activity_samples (
    activity_id bigint REFERENCES garmin.activities ON DELETE CASCADE,
    ts          timestamptz,
    hr          smallint,
    speed_ms    real,
    cadence     real,
    power       real,
    elevation_m real,
    lat         double precision,
    lon         double precision,
    distance_m  real,
    PRIMARY KEY (activity_id, ts)
);
CREATE TABLE IF NOT EXISTS garmin.activity_files (
    activity_id   bigint PRIMARY KEY REFERENCES garmin.activities ON DELETE CASCADE,
    file_name     text,
    bytes         integer,
    downloaded_at timestamptz NOT NULL DEFAULT now()
);

-- ---------- служебное ----------
CREATE TABLE IF NOT EXISTS garmin.sync_state (
    key   text PRIMARY KEY,
    value text NOT NULL
);

-- ---------- представления для выгрузки ----------
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
"""

DAY_TABLES = ["sleep", "heart", "stress_energy", "movement", "training", "body", "hydration"]

SAMPLE_TABLES = {  # таблица: (столбцы, ключ)
    "hr_samples": (["ts", "hr"], ["ts"]),
    "stress_samples": (["ts", "stress"], ["ts"]),
    "body_battery_samples": (["ts", "level"], ["ts"]),
    "respiration_samples": (["ts", "breaths"], ["ts"]),
    "hrv_samples": (["ts", "hrv"], ["ts"]),
    "steps_15min": (["ts_start", "ts_end", "steps", "activity_level"], ["ts_start"]),
    "sleep_stages": (["ts_start", "ts_end", "stage", "level"], ["ts_start"]),
}

ACTIVITY_CHILDREN = {  # таблица: (столбцы, ключ, источник в raw.activity)
    "activity_laps": (["activity_id", "lap_no", "start_utc", "duration_s", "distance_m", "avg_hr", "max_hr",
                       "avg_speed_ms", "elev_gain_m", "calories"], ["activity_id", "lap_no"], "splits"),
    "activity_hr_zones": (["activity_id", "zone", "seconds", "low_bpm"], ["activity_id", "zone"], "hr_zones"),
    "strength_sets": (["activity_id", "set_no", "set_type", "start_utc", "duration_s", "exercise", "category",
                       "reps", "weight_kg"], ["activity_id", "set_no"], "exercise_sets"),
    "activity_samples": (["activity_id", "ts", "hr", "speed_ms", "cadence", "power", "elevation_m", "lat", "lon",
                          "distance_m"], ["activity_id", "ts"], "details"),
}


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()


# =====================================================================
# Garmin
# =====================================================================

def login(interactive: bool):
    from garminconnect import Garmin
    try:
        g = Garmin()
        g.login(TOKENS)
        return g
    except Exception as e:
        if not interactive:
            log(f"Вход по сохранённым токенам не удался ({type(e).__name__}). "
                "Нужен повторный вход: docker compose run --rm collector python sync.py --login")
            sys.exit(1)
    from getpass import getpass
    email = input("Garmin email: ")
    pwd = getpass("Garmin пароль: ")
    g = Garmin(email, pwd, prompt_mfa=lambda: input("Код MFA: "))
    g.login(TOKENS)
    try:  # на случай версии библиотеки, которая не сохраняет токены сама
        g.garth.dump(TOKENS)
    except Exception:
        pass
    log("Вход выполнен, токены сохранены в /tokens")
    return g


class Api:
    """Обёртка над garminconnect: паузы, распознавание лимита 429, по одному предупреждению на ошибку за проход."""

    def __init__(self, g):
        self.g = g
        self.warned: set = set()
        self.calls = 0

    def call(self, label: str, method: str, *args, **kwargs) -> Any:
        m = getattr(self.g, method, None)
        if m is None:
            if method not in self.warned:
                log(f"  метод {method} недоступен в этой версии garminconnect — пропускаю «{label}»")
                self.warned.add(method)
            return None
        time.sleep(PAUSE_CALL)
        self.calls += 1
        try:
            return m(*args, **kwargs)
        except Exception as e:
            text = f"{type(e).__name__}: {e}"
            if "429" in text or "Too Many" in text:
                raise RateLimited(text)
            key = (label, type(e).__name__)
            if key not in self.warned:
                log(f"  {label}: {text[:200]}")
                self.warned.add(key)
            return None


# имя в raw.daily: метод garminconnect (все принимают дату 'ГГГГ-ММ-ДД')
DAY_ENDPOINTS = {
    "user_summary": "get_user_summary",
    "heart_rates": "get_heart_rates",
    "hrv": "get_hrv_data",
    "respiration": "get_respiration_data",
    "spo2": "get_spo2_data",
    "max_metrics": "get_max_metrics",
    "sleep": "get_sleep_data",
    "stress": "get_stress_data",
    "body_battery": "get_body_battery",
    "steps": "get_steps_data",
    "training_readiness": "get_training_readiness",
    "training_status": "get_training_status",
    "hydration": "get_hydration_data",
    "body_composition": "get_body_composition",
    "fitness_age": "get_fitnessage_data",
    "endurance_score": "get_endurance_score",
}

STRENGTH_TYPES = {"strength_training", "hiit", "indoor_cardio", "fitness_equipment"}


def fetch_day(api: Api, day: str) -> dict[str, Any]:
    return {name: api.call(name, method, day) for name, method in DAY_ENDPOINTS.items()}


def fetch_activity(api: Api, aid: int, item: dict) -> dict[str, Any]:
    raw: dict[str, Any] = {"list": item}
    raw["summary"] = api.call("тренировка", "get_activity", aid)
    raw["splits"] = api.call("круги", "get_activity_splits", aid)
    raw["hr_zones"] = api.call("пульсовые зоны", "get_activity_hr_in_timezones", aid)
    typ = dig(item, "activityType", "typeKey") or ""
    if typ in STRENGTH_TYPES or item.get("totalSets") or item.get("activeSets"):
        raw["exercise_sets"] = api.call("подходы", "get_activity_exercise_sets", aid)
    raw["details"] = api.call("данные тренировки", "get_activity_details", aid)
    return raw


# =====================================================================
# разбор ответов Garmin
# =====================================================================

SLEEP_STAGE = {0: "deep", 1: "light", 2: "rem", 3: "awake"}


def latest_entry(v: Any) -> Any:
    """Из списка записей за день берём последнюю по времени (готовность к тренировке пересчитывается в течение дня)."""
    if isinstance(v, list):
        items = [x for x in v if isinstance(x, dict)]
        if not items:
            return None
        return max(items, key=lambda x: str(x.get("timestampLocal") or x.get("timestamp") or ""))
    return v


def parse_day(raw: dict[str, Any]) -> tuple[dict[str, dict], dict[str, list[tuple]]]:
    us = raw.get("user_summary") or {}
    hr = raw.get("heart_rates") or {}
    hs = dig(raw.get("hrv"), "hrvSummary") or {}
    sl = raw.get("sleep") or {}
    sd = sl.get("dailySleepDTO") or {} if isinstance(sl, dict) else {}
    resp = raw.get("respiration")
    spo2 = raw.get("spo2")
    st = raw.get("stress") or {}
    bb = raw.get("body_battery")
    bb0 = bb[0] if isinstance(bb, list) and bb and isinstance(bb[0], dict) else (bb if isinstance(bb, dict) else {})
    mm = raw.get("max_metrics")
    ts_ = raw.get("training_status")
    tr = latest_entry(raw.get("training_readiness"))
    bc = raw.get("body_composition")
    bc = bc if isinstance(bc, dict) else {}
    bsrc = dig(bc, "totalAverage")
    bsrc = bsrc if isinstance(bsrc, dict) else {}
    if bsrc.get("weight") is None:
        lst = [x for x in bc.get("dateWeightList") or [] if isinstance(x, dict) and x.get("weight") is not None]
        bsrc = lst[-1] if lst else {}
    hyd = raw.get("hydration")
    us = us if isinstance(us, dict) else {}
    st = st if isinstance(st, dict) else {}
    hr = hr if isinstance(hr, dict) else {}

    rows = {
        "sleep": {
            "sleep_start": ms_to_ts(sd.get("sleepStartTimestampGMT")),
            "sleep_end": ms_to_ts(sd.get("sleepEndTimestampGMT")),
            "total_s": to_int(sd.get("sleepTimeSeconds")),
            "deep_s": to_int(sd.get("deepSleepSeconds")),
            "light_s": to_int(sd.get("lightSleepSeconds")),
            "rem_s": to_int(sd.get("remSleepSeconds")),
            "awake_s": to_int(sd.get("awakeSleepSeconds")),
            "score": to_int(dig(sd, "sleepScores", "overall", "value")),
            "quality": dig(sd, "sleepScores", "overall", "qualifierKey"),
            "avg_stress": num(sd.get("avgSleepStress")),
            "hr_avg": to_int(first(sd.get("avgHeartRate"), sl.get("restingHeartRate") if isinstance(sl, dict) else None)),
            "resp_avg": num(first(sd.get("averageRespirationValue"), find(resp, "avgSleepRespirationValue"))),
            "spo2_avg": to_int(first(sd.get("averageSpO2Value"), find(spo2, "averageSpO2", "avgSleepSpO2"))),
            "spo2_min": to_int(first(sd.get("lowestSpO2Value"), find(spo2, "lowestSpO2"))),
        },
        "heart": {
            "rhr": to_int(first(find(hr, "restingHeartRate"), us.get("restingHeartRate"))),
            "rhr_7d": to_int(first(find(hr, "lastSevenDaysAvgRestingHeartRate"),
                                   us.get("lastSevenDaysAvgRestingHeartRate"))),
            "hr_min": to_int(first(hr.get("minHeartRate") if isinstance(hr, dict) else None, us.get("minHeartRate"))),
            "hr_max": to_int(first(hr.get("maxHeartRate") if isinstance(hr, dict) else None, us.get("maxHeartRate"))),
            "hrv_night": to_int(hs.get("lastNightAvg")),
            "hrv_night_max5": to_int(hs.get("lastNight5MinHigh")),
            "hrv_week": to_int(hs.get("weeklyAvg")),
            "hrv_status": hs.get("status"),
            "hrv_baseline_low": to_int(dig(hs, "baseline", "balancedLow")),
            "hrv_baseline_high": to_int(dig(hs, "baseline", "balancedUpper")),
        },
        "stress_energy": {
            "stress_avg": to_int(first(us.get("averageStressLevel"), st.get("avgStressLevel") if isinstance(st, dict) else None)),
            "stress_max": to_int(first(us.get("maxStressLevel"), st.get("maxStressLevel") if isinstance(st, dict) else None)),
            "rest_s": to_int(us.get("restStressDuration")),
            "low_s": to_int(us.get("lowStressDuration")),
            "medium_s": to_int(us.get("mediumStressDuration")),
            "high_s": to_int(us.get("highStressDuration")),
            "bb_max": to_int(us.get("bodyBatteryHighestValue")),
            "bb_min": to_int(us.get("bodyBatteryLowestValue")),
            "bb_wake": to_int(us.get("bodyBatteryAtWakeTime")),
            "bb_charged": to_int(first(us.get("bodyBatteryChargedValue"), bb0.get("charged"))),
            "bb_drained": to_int(first(us.get("bodyBatteryDrainedValue"), bb0.get("drained"))),
        },
        "movement": {
            "steps": to_int(us.get("totalSteps")),
            "step_goal": to_int(us.get("dailyStepGoal")),
            "distance_m": to_int(us.get("totalDistanceMeters")),
            "floors_up": num(us.get("floorsAscended")),
            "floors_down": num(us.get("floorsDescended")),
            "calories_total": to_int(us.get("totalKilocalories")),
            "calories_active": to_int(us.get("activeKilocalories")),
            "calories_bmr": to_int(us.get("bmrKilocalories")),
            "intensity_moderate_min": to_int(us.get("moderateIntensityMinutes")),
            "intensity_vigorous_min": to_int(us.get("vigorousIntensityMinutes")),
            "sedentary_s": to_int(us.get("sedentarySeconds")),
            "active_s": to_int(us.get("activeSeconds")),
            "highly_active_s": to_int(us.get("highlyActiveSeconds")),
            "resp_waking": num(find(resp, "avgWakingRespirationValue")),
        },
        "training": {
            "readiness_score": to_int(find(tr, "score")),
            "readiness_level": find(tr, "level"),
            "training_status": find(ts_, "trainingStatusFeedbackPhrase"),
            "load_acute": num(find(ts_, "dailyTrainingLoadAcute")),
            "load_chronic": num(find(ts_, "dailyTrainingLoadChronic")),
            "load_ratio": num(find(ts_, "dailyAcuteChronicWorkloadRatio"), 2),
            "vo2max_run": num(find(find(mm, "generic"), "vo2MaxPreciseValue", "vo2MaxValue")),
            "vo2max_bike": num(find(find(mm, "cycling"), "vo2MaxPreciseValue", "vo2MaxValue")),
            "fitness_age": num(find(raw.get("fitness_age"), "fitnessAge")),
            "endurance_score": to_int(find(raw.get("endurance_score"), "overallScore")),
        },
        "body": {
            "weight_kg": grams_to_kg(bsrc.get("weight")),
            "bmi": num(bsrc.get("bmi")),
            "body_fat_pct": num(bsrc.get("bodyFat")),
            "muscle_kg": grams_to_kg(bsrc.get("muscleMass")),
            "bone_kg": grams_to_kg(bsrc.get("boneMass")),
            "body_water_pct": num(bsrc.get("bodyWater")),
        },
        "hydration": {
            "intake_ml": to_int(find(hyd, "valueInML")),
            "goal_ml": to_int(find(hyd, "goalInML")),
            "sweat_loss_ml": to_int(find(hyd, "sweatLossInML")),
        },
    }

    def series(arr: Any, vi: int = 1, minimum: float | None = None, as_int: bool = True) -> list[tuple]:
        out: dict[dt.datetime, Any] = {}
        for it in arr or []:
            if not isinstance(it, list) or len(it) <= vi:
                continue
            ts = ms_to_ts(it[0])
            v = num(it[vi], 1)
            if ts is None or v is None or (minimum is not None and v < minimum):
                continue
            out[ts] = int(v) if as_int else v
        return sorted(out.items())

    bb_arr = st.get("bodyBatteryValuesArray") if isinstance(st, dict) else None
    bb_idx = 2 if bb_arr and isinstance(bb_arr[0], list) and len(bb_arr[0]) >= 3 else 1

    steps = []
    for it in raw.get("steps") or []:
        if isinstance(it, dict) and gmt_to_ts(it.get("startGMT")):
            steps.append((gmt_to_ts(it.get("startGMT")), gmt_to_ts(it.get("endGMT")),
                          to_int(it.get("steps")), it.get("primaryActivityLevel")))

    stages = []
    for it in (sl.get("sleepLevels") if isinstance(sl, dict) else None) or []:
        if isinstance(it, dict) and gmt_to_ts(it.get("startGMT")):
            lvl = num(it.get("activityLevel"), 1)
            stages.append((gmt_to_ts(it.get("startGMT")), gmt_to_ts(it.get("endGMT")),
                           SLEEP_STAGE.get(int(lvl)) if lvl is not None else None, lvl))

    hrv_pts = {}
    for it in dig(raw.get("hrv"), "hrvReadings") or []:
        if isinstance(it, dict):
            ts = gmt_to_ts(it.get("readingTimeGMT"))
            if ts and it.get("hrvValue") is not None:
                hrv_pts[ts] = to_int(it.get("hrvValue"))

    samples = {
        "hr_samples": series(hr.get("heartRateValues") if isinstance(hr, dict) else None, minimum=1),
        "stress_samples": series(st.get("stressValuesArray") if isinstance(st, dict) else None, minimum=0),
        "body_battery_samples": series(bb_arr, vi=bb_idx, minimum=0),
        "respiration_samples": series(find(resp, "respirationValuesArray"), minimum=1, as_int=False),
        "hrv_samples": sorted(hrv_pts.items()),
        "steps_15min": steps,
        "sleep_stages": stages,
    }
    return rows, samples


def parse_activity(aid: int, raw: dict[str, Any]) -> tuple[dict, dict[str, list[tuple] | None]]:
    item = raw.get("list") or {}
    summ = raw.get("summary") or {}
    s = summ.get("summaryDTO") or {} if isinstance(summ, dict) else {}

    def f(*keys: str) -> Any:
        return first(*(item.get(k) for k in keys), *(s.get(k) for k in keys))

    start_local = parse_dt(f("startTimeLocal"))
    row = {
        "activity_id": aid,
        "day": start_local.date() if start_local else None,
        "start_local": start_local,
        "start_utc": gmt_to_ts(f("startTimeGMT")),
        "type": first(dig(item, "activityType", "typeKey"), dig(summ, "activityTypeDTO", "typeKey")),
        "name": first(item.get("activityName"), summ.get("activityName") if isinstance(summ, dict) else None),
        "duration_s": num(f("duration")),
        "moving_s": num(f("movingDuration")),
        "elapsed_s": num(f("elapsedDuration")),
        "distance_m": num(f("distance")),
        "calories": num(f("calories")),
        "avg_hr": to_int(f("averageHR")),
        "max_hr": to_int(f("maxHR")),
        "avg_speed_ms": num(f("averageSpeed"), 3),
        "max_speed_ms": num(f("maxSpeed"), 3),
        "elev_gain_m": num(f("elevationGain")),
        "elev_loss_m": num(f("elevationLoss")),
        "avg_cadence": num(f("averageRunningCadenceInStepsPerMinute", "averageBikingCadenceInRevPerMinute",
                             "averageRunCadence", "averageBikeCadence")),
        "avg_power": num(f("avgPower", "averagePower")),
        "max_power": num(f("maxPower")),
        "norm_power": num(f("normPower", "normalizedPower")),
        "te_aerobic": num(f("aerobicTrainingEffect", "trainingEffect")),
        "te_anaerobic": num(f("anaerobicTrainingEffect")),
        "training_load": num(f("activityTrainingLoad")),
        "vo2max": num(f("vO2MaxValue")),
        "steps": to_int(f("steps")),
        "total_sets": to_int(f("totalSets", "activeSets")),
        "total_reps": to_int(f("totalReps")),
        "device_id": to_int(f("deviceId")),
    }

    children: dict[str, list[tuple] | None] = {k: None for k in ACTIVITY_CHILDREN}  # None = источника нет, не трогаем

    if raw.get("splits") is not None:
        laps = []
        for i, lp in enumerate(find(raw["splits"], "lapDTOs") or [], 1):
            if isinstance(lp, dict):
                laps.append((aid, to_int(first(lp.get("lapIndex"), i)), gmt_to_ts(lp.get("startTimeGMT")),
                             num(lp.get("duration")), num(lp.get("distance")), to_int(lp.get("averageHR")),
                             to_int(lp.get("maxHR")), num(lp.get("averageSpeed"), 3), num(lp.get("elevationGain")),
                             num(lp.get("calories"))))
        children["activity_laps"] = list({(r[0], r[1]): r for r in laps}.values())

    if raw.get("hr_zones") is not None:
        zones = []
        for z in raw["hr_zones"] if isinstance(raw["hr_zones"], list) else []:
            if isinstance(z, dict) and z.get("zoneNumber") is not None:
                zones.append((aid, to_int(z.get("zoneNumber")), num(z.get("secsInZone")), to_int(z.get("zoneLowBoundary"))))
        children["activity_hr_zones"] = zones

    if raw.get("exercise_sets") is not None:
        sets = []
        for i, es in enumerate(find(raw["exercise_sets"], "exerciseSets") or []):
            if not isinstance(es, dict):
                continue
            ex = [e for e in es.get("exercises") or [] if isinstance(e, dict)]
            best = max(ex, key=lambda e: num(e.get("probability")) or 0) if ex else {}
            sets.append((aid, to_int(first(es.get("messageIndex"), i)), es.get("setType"), gmt_to_ts(es.get("startTime")),
                         num(es.get("duration")), first(best.get("name"), best.get("category")), best.get("category"),
                         to_int(es.get("repetitionCount")), set_weight_kg(es.get("weight"))))
        children["strength_sets"] = list({(r[0], r[1]): r for r in sets}.values())

    if raw.get("details") is not None:
        d = raw["details"] if isinstance(raw["details"], dict) else {}
        idx = {m.get("key"): m.get("metricsIndex") for m in d.get("metricDescriptors") or [] if isinstance(m, dict)}

        def col(metrics: list, *keys: str) -> Any:
            for k in keys:
                i = idx.get(k)
                if i is not None and i < len(metrics) and metrics[i] is not None:
                    return metrics[i]
            return None

        pts: dict[dt.datetime, tuple] = {}
        for r in d.get("activityDetailMetrics") or []:
            m = r.get("metrics") if isinstance(r, dict) else None
            if not m:
                continue
            ts = ms_to_ts(col(m, "directTimestamp"))
            if ts is None:
                continue
            pts[ts] = (aid, ts, to_int(col(m, "directHeartRate")), num(col(m, "directSpeed"), 3),
                       num(col(m, "directRunCadence", "directBikeCadence", "directDoubleCadence")),
                       num(col(m, "directPower")), num(col(m, "directElevation")),
                       col(m, "directLatitude"), col(m, "directLongitude"), num(col(m, "sumDistance")))
        children["activity_samples"] = [pts[k] for k in sorted(pts)]

    return row, children


# =====================================================================
# запись в базу
# =====================================================================

def upsert(cur, table: str, cols: list[str], keys: list[str], rows: Iterable[tuple], stamp: bool = False) -> None:
    rows = list(rows)
    if not rows:
        return
    rest = [c for c in cols if c not in keys]
    sets = [f"{c} = EXCLUDED.{c}" for c in rest] + (["updated_at = now()"] if stamp else [])
    action = f"DO UPDATE SET {', '.join(sets)}" if sets else "DO NOTHING"
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
           f"ON CONFLICT ({', '.join(keys)}) {action}")
    cur.executemany(sql, rows)


def write_day(cur, day: dt.date, rows: dict[str, dict], samples: dict[str, list[tuple]]) -> None:
    for table, row in rows.items():
        if all(v is None for v in row.values()):
            continue
        cols = ["day"] + list(row)
        upsert(cur, f"garmin.{table}", cols, ["day"], [tuple([day] + list(row.values()))], stamp=True)
    for table, data in samples.items():
        cols, keys = SAMPLE_TABLES[table]
        upsert(cur, f"garmin.{table}", cols, keys, data)


def save_day(conn, day: str, raw: dict[str, Any]) -> None:
    rows, samples = parse_day(raw)
    with conn.cursor() as cur:
        upsert(cur, "raw.daily", ["day", "endpoint", "payload"], ["day", "endpoint"],
               [(day, name, Jsonb(payload)) for name, payload in raw.items()])
        cur.execute("UPDATE raw.daily SET fetched_at = now() WHERE day = %s", (day,))
        write_day(cur, as_date(day), rows, samples)
    conn.commit()


def write_activity(cur, aid: int, raw: dict[str, Any]) -> dict:
    row, children = parse_activity(aid, raw)
    upsert(cur, "garmin.activities", list(row), ["activity_id"], [tuple(row.values())], stamp=True)
    for table, data in children.items():
        if data is None:
            continue  # этот запрос не удался — оставляем прежние строки
        cols, keys, _ = ACTIVITY_CHILDREN[table]
        cur.execute(f"DELETE FROM garmin.{table} WHERE activity_id = %s", (aid,))
        upsert(cur, f"garmin.{table}", cols, keys, data)
    return row


def save_activity(conn, aid: int, raw: dict[str, Any]) -> dict:
    with conn.cursor() as cur:
        upsert(cur, "raw.activity", ["activity_id", "endpoint", "payload"], ["activity_id", "endpoint"],
               [(aid, name, Jsonb(payload)) for name, payload in raw.items() if payload is not None])
        cur.execute("UPDATE raw.activity SET fetched_at = now() WHERE activity_id = %s", (aid,))
        row = write_activity(cur, aid, raw)
    conn.commit()
    return row


def get_state(conn, key: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM garmin.sync_state WHERE key = %s", (key,))
        r = cur.fetchone()
    return r[0] if r else None


def set_state(conn, key: str, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO garmin.sync_state (key, value) VALUES (%s, %s)
                       ON CONFLICT (key) DO UPDATE SET value = GREATEST(garmin.sync_state.value, EXCLUDED.value)""",
                    (key, value))
    conn.commit()


def history_start(conn) -> dt.date:
    """Откуда начинать при первом запуске версии 2: самый ранний день в базе или BACKFILL_FROM."""
    with conn.cursor() as cur:
        cur.execute("SELECT min(day) FROM raw.daily")
        r = cur.fetchone()
    cands = [d for d in (as_date(r[0]) if r and r[0] else None,
                         as_date(BACKFILL_FROM) if BACKFILL_FROM else None) if d]
    return min(cands) if cands else now().date() - dt.timedelta(days=BACKFILL_DAYS_DEFAULT)


def window_start(conn, key: str) -> dt.date:
    done = get_state(conn, key)
    if done:
        return min(as_date(done), now().date()) - dt.timedelta(days=RESYNC_DAYS)
    return history_start(conn)


# =====================================================================
# сбор
# =====================================================================

def with_rate_limit(fn, what: str):
    """Один повтор после паузы при ошибке 429. При повторной — RateLimited наверх."""
    try:
        return fn()
    except RateLimited:
        log(f"Garmin ограничил частоту запросов ({what}) — пауза {RATE_LIMIT_WAIT // 60} минут")
        time.sleep(RATE_LIMIT_WAIT)
        return fn()


def sync_days(api: Api, conn) -> bool:
    """Возвращает False, если упёрлись в лимит Garmin."""
    day = window_start(conn, "days_done_until")
    today = now().date()
    total = (today - day).days + 1
    log(f"Дни: {day} … {today} ({total} дн.)")
    done = 0
    while day <= today:
        ds = day.isoformat()
        try:
            raw = with_rate_limit(lambda: fetch_day(api, ds), ds)
        except RateLimited:
            log("Снова ограничение — прерываю, продолжу со следующего прохода с этого же места")
            return False
        save_day(conn, ds, raw)
        set_state(conn, "days_done_until", ds)
        done += 1
        if done % 30 == 0:
            log(f"  … {done}/{total}")
        day += dt.timedelta(days=1)
        time.sleep(PAUSE_DAY)
    log(f"Дни: готово {done}")
    return True


def download_fit(api: Api, conn, aid: int, row: dict) -> None:
    fit_dir = OUT / "fit"
    with conn.cursor() as cur:
        cur.execute("SELECT file_name FROM garmin.activity_files WHERE activity_id = %s", (aid,))
        r = cur.fetchone()
    if r and (fit_dir / r[0]).exists():
        return
    fmt = getattr(getattr(type(api.g), "ActivityDownloadFormat", None), "ORIGINAL", None)
    data = (api.call("FIT-файл", "download_activity", aid, dl_fmt=fmt) if fmt is not None
            else api.call("FIT-файл", "download_activity", aid))
    if not data:
        return
    fit_dir.mkdir(parents=True, exist_ok=True)
    name = f"{row.get('day') or 'unknown'}_{aid}_{row.get('type') or 'activity'}.zip"
    (fit_dir / name).write_bytes(data)
    with conn.cursor() as cur:
        upsert(cur, "garmin.activity_files", ["activity_id", "file_name", "bytes"], ["activity_id"],
               [(aid, name, len(data))])
    conn.commit()


def sync_activities(api: Api, conn) -> bool:
    start = window_start(conn, "activities_done_until")
    today = now().date()
    try:
        items = with_rate_limit(lambda: api.call("список тренировок", "get_activities_by_date",
                                                 start.isoformat(), today.isoformat()), "список тренировок")
    except RateLimited:
        log("Тренировки: ограничение Garmin — пропускаю до следующего прохода")
        return False
    items = sorted([i for i in items or [] if isinstance(i, dict) and i.get("activityId")],
                   key=lambda i: str(i.get("startTimeLocal") or ""))
    with conn.cursor() as cur:
        cur.execute("SELECT activity_id FROM garmin.activities")
        known = {int(r[0]) for r in cur.fetchall()}
    fresh_from = today - dt.timedelta(days=RESYNC_DAYS)
    log(f"Тренировки: {start} … {today}, найдено {len(items)}")
    loaded = 0
    for item in items:
        aid = int(item["activityId"])
        st = parse_dt(item.get("startTimeLocal"))
        day = st.date() if st else today
        if aid in known and day < fresh_from:
            set_state(conn, "activities_done_until", day.isoformat())
            continue
        try:
            raw = with_rate_limit(lambda: fetch_activity(api, aid, item), f"тренировка {aid}")
            row = save_activity(conn, aid, raw)
            if DOWNLOAD_FIT:
                with_rate_limit(lambda: download_fit(api, conn, aid, row), f"FIT {aid}")
        except RateLimited:
            log("Снова ограничение — прерываю, продолжу со следующего прохода с этого же места")
            return False
        set_state(conn, "activities_done_until", day.isoformat())
        loaded += 1
        if loaded % 20 == 0:
            log(f"  … {loaded} тренировок")
        time.sleep(PAUSE_ACTIVITY)
    set_state(conn, "activities_done_until", today.isoformat())
    log(f"Тренировки: загружено {loaded}")
    return True


# =====================================================================
# выгрузка в CSV, бэкап, Google Drive
# =====================================================================

EXPORTS = [
    ("garmin_daily_metrics.csv", "SELECT * FROM garmin.daily_overview ORDER BY day"),
    ("garmin_activities.csv", "SELECT * FROM garmin.activities ORDER BY start_local"),
    ("garmin_strength_sets.csv", "SELECT * FROM garmin.strength_log ORDER BY start_local, set_no"),
    ("activities/garmin_activity_laps.csv",
     "SELECT a.day, a.type, a.name, l.* FROM garmin.activity_laps l JOIN garmin.activities a USING (activity_id) "
     "ORDER BY a.start_local, l.lap_no"),
    ("activities/garmin_activity_hr_zones.csv",
     "SELECT a.day, a.type, a.name, z.* FROM garmin.activity_hr_zones z JOIN garmin.activities a USING (activity_id) "
     "ORDER BY a.start_local, z.zone"),
    ("activities/garmin_activity_samples.csv",
     "SELECT * FROM garmin.activity_samples ORDER BY activity_id, ts"),
    ("intraday/garmin_hr.csv", "SELECT ts, hr FROM garmin.hr_samples ORDER BY ts"),
    ("intraday/garmin_stress.csv", "SELECT ts, stress FROM garmin.stress_samples ORDER BY ts"),
    ("intraday/garmin_body_battery.csv", "SELECT ts, level FROM garmin.body_battery_samples ORDER BY ts"),
    ("intraday/garmin_respiration.csv", "SELECT ts, breaths FROM garmin.respiration_samples ORDER BY ts"),
    ("intraday/garmin_hrv_night.csv", "SELECT ts, hrv FROM garmin.hrv_samples ORDER BY ts"),
    ("intraday/garmin_steps_15min.csv", "SELECT * FROM garmin.steps_15min ORDER BY ts_start"),
    ("intraday/garmin_sleep_stages.csv", "SELECT * FROM garmin.sleep_stages ORDER BY ts_start"),
]


def cell(v: Any) -> Any:
    """Время — по Москве без смещения, чтобы Google Таблицы и Excel распознавали его как дату."""
    if v is None:
        return ""
    if isinstance(v, dt.datetime):
        if v.tzinfo:
            v = v.astimezone(TZ)
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, dt.date):
        return v.isoformat()
    return v


def export_csv(conn) -> None:
    for rel, sql in EXPORTS:
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with conn.cursor() as cur:
            cur.execute(sql)
            header = [d[0] for d in cur.description]
            rows = cur.fetchall()
        with tmp.open("w", encoding="utf-8-sig", newline="") as f:  # BOM — для кириллицы в Excel
            w = csv.writer(f)
            w.writerow(header)
            w.writerows([cell(v) for v in r] for r in rows)
        tmp.replace(path)
    log(f"CSV: {len(EXPORTS)} файлов → {OUT}")


def backup() -> Path | None:
    DUMPS.mkdir(parents=True, exist_ok=True)
    name = DUMPS / f"garmin_{now():%Y%m%d_%H%M}.sql.gz"
    r = subprocess.run(f"pg_dump '{PG_DSN}' | gzip > '{name}'", shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"Бэкап: ошибка {r.stderr.strip()[:300]}")
        return None
    for old in sorted(DUMPS.glob("garmin_*.sql.gz"))[:-KEEP_DUMPS]:
        old.unlink(missing_ok=True)
    log(f"Бэкап: {name.name}")
    return name


def rclone(*args: str) -> bool:
    r = subprocess.run(["rclone", *args], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"Google Drive: ошибка rclone {args[0]}: {r.stderr.strip()[:300]}")
    return r.returncode == 0


def upload(dump: Path | None) -> None:
    if not RCLONE_REMOTE:
        log("Google Drive: не настроен (RCLONE_REMOTE пуст) — пропускаю")
        return
    # CSV и FIT-файлы; rclone copy отправляет только изменившиеся файлы
    ok = rclone("copy", str(OUT), RCLONE_REMOTE, "--exclude", "*.tmp", "--exclude", "garmin_health.json")
    if dump:
        ok &= rclone("copyto", str(dump), f"{RCLONE_REMOTE}/backups/{dump.name}")
        rclone("delete", f"{RCLONE_REMOTE}/backups", "--min-age", f"{KEEP_DUMPS}d")
    if ok:
        log("Google Drive: таблицы, FIT-файлы и бэкап загружены")


# =====================================================================
# проход, пересборка, расписание
# =====================================================================

def connect():
    conn = psycopg.connect(PG_DSN)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'Europe/Moscow'")
    return conn


def run_once() -> None:
    g = login(interactive=False)
    api = Api(g)
    t0 = time.time()
    with connect() as conn:
        ensure_schema(conn)
        if sync_days(api, conn):
            sync_activities(api, conn)
        export_csv(conn)
    log(f"Проход: {api.calls} запросов к Garmin, {round((time.time() - t0) / 60, 1)} мин")
    upload(backup())


def reparse() -> None:
    """Пересобирает garmin.* из raw.* — например, после исправления разбора. К Garmin не обращается."""
    with connect() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT day, endpoint, payload FROM raw.daily ORDER BY day")
            daily = cur.fetchall()
            cur.execute("SELECT activity_id, endpoint, payload FROM raw.activity ORDER BY activity_id")
            acts = cur.fetchall()
        by_day: dict[dt.date, dict] = {}
        for day, ep, payload in daily:
            by_day.setdefault(as_date(day), {})[ep] = as_json(payload)
        by_act: dict[int, dict] = {}
        for aid, ep, payload in acts:
            by_act.setdefault(int(aid), {})[ep] = as_json(payload)
        with conn.cursor() as cur:
            for day, raw in by_day.items():
                rows, samples = parse_day(raw)
                write_day(cur, day, rows, samples)
            for aid, raw in by_act.items():
                write_activity(cur, aid, raw)
        conn.commit()
        log(f"Пересборка: {len(by_day)} дн., {len(by_act)} тренировок")
        export_csv(conn)


def next_run(after: dt.datetime) -> dt.datetime:
    cands = []
    for t in RUN_TIMES:
        h, m = map(int, t.split(":"))
        c = after.replace(hour=h, minute=m, second=0, microsecond=0)
        if c <= after:
            c += dt.timedelta(days=1)
        cands.append(c)
    return min(cands)


def safe_run() -> None:
    try:
        run_once()
    except SystemExit:
        # нет токенов или вход не удался — не перезапускаем контейнер в цикле, ждём следующего запуска
        log("Проход пропущен: нужен вход в Garmin (см. сообщение выше)")
    except Exception as e:
        log(f"Ошибка прохода: {type(e).__name__}: {e}")


def service() -> None:
    log(f"Служба запущена (версия 2), расписание: {', '.join(RUN_TIMES)} ({TZ.key})")
    if os.environ.get("RUN_ON_START", "1") == "1":
        safe_run()
    while True:
        nxt = next_run(now())
        log(f"Следующий запуск: {nxt:%Y-%m-%d %H:%M}")
        time.sleep(max(1, (nxt - now()).total_seconds()))
        safe_run()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true", help="интерактивный вход в Garmin")
    ap.add_argument("--once", action="store_true", help="один проход и выход")
    ap.add_argument("--reparse", action="store_true", help="пересобрать таблицы из raw.* без запросов к Garmin")
    a = ap.parse_args()
    if a.login:
        login(interactive=True)
    elif a.once:
        run_once()
    elif a.reparse:
        reparse()
    else:
        service()


if __name__ == "__main__":
    main()
