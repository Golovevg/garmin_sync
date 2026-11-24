-- Выполняется только при самом первом создании базы (пустой том pgdata).
-- Все таблицы создаёт и обновляет сам сборщик (collector/sync.py, SCHEMA_SQL) при каждом запуске.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS garmin;
