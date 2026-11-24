-- Runs only when the database is first initialized (empty pgdata volume).
-- The collector creates and updates all tables on each run (collector/sync.py, SCHEMA_SQL).
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS garmin;
