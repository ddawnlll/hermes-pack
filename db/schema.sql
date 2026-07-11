-- db/schema.sql
-- Hephaestus v0.6 Postgres bootstrap (DL-1, #95)
--
-- Phase A of the file -> Postgres cutover (A-4 #79). This file creates
-- the bootstrap database, the pgvector extension, and the canonical
-- tables that DL-2 (#97) will populate with the candidate manifest
-- schema. We do NOT create candidate tables here — that is DL-2's job.
--
-- Apply order (see db/migrations/000_initial.sql for the explicit list):
--   1. CREATE EXTENSION vector;
--   2. CREATE SCHEMA hephaestus;
--   3. CREATE TABLE hephaestus.control_state (mirror of templates/control.yaml)
--   4. CREATE TABLE hephaestus.migration_log (idempotency for migrations)
--
-- The control_state table is the canonical mirror in Phase A; in Phase B
-- (A-4 #79) it becomes the source of truth and the YAML is the export.

\set ON_ERROR_STOP on

-- 1. pgvector extension. Available since PG 13; we use the standard name.
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. The hephaestus schema isolates our tables from any other workloads
--    sharing the same database (e.g. a developer running this locally
--    alongside another project).
CREATE SCHEMA IF NOT EXISTS hephaestus;

-- 3. control_state: mirrors templates/control.yaml:mode in Phase A.
--    See A-4 #79 for the kill/pause/freeze OR'ling invariant. The
--    `mode` enum is the same as control.schema.json's enum, kept in
--    sync by the migration framework.
CREATE TABLE IF NOT EXISTS hephaestus.control_state (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    mode            TEXT NOT NULL CHECK (mode IN ('live', 'paused', 'frozen', 'killed')),
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_observed_by TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Seed: if no row, we start in `live` (will be OR'd with the file
-- canonical in Phase A). The Orchestrator writes this row on every
-- state change; the file is read on every read; OR'ling per A-4 #79.
INSERT INTO hephaestus.control_state (id, mode, last_observed_by)
VALUES (1, 'live', 'db.schema.sql bootstrap')
ON CONFLICT (id) DO NOTHING;

-- 4. migration_log: tracks which migrations have been applied. Used by
--    db/connection.py's `migrate()` function to make the migration
--    runner idempotent. Each migration registers one row.
CREATE TABLE IF NOT EXISTS hephaestus.migration_log (
    migration_id   TEXT PRIMARY KEY,
    applied_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_by     TEXT NOT NULL,
    checksum       TEXT NOT NULL
);

COMMENT ON SCHEMA hephaestus IS
    'Hephaestus v0.6 Postgres tables (DL-1 #95, DL-2 #97, DL-4 #98). '
    'Phase A: file canonical + DB mirror. Phase B: DB canonical + file export.';
COMMENT ON TABLE hephaestus.control_state IS
    'Mirror of templates/control.yaml. A-4 #79 OR''ling invariant: '
    'effective mode is OR of file + DB, evaluated killed > frozen > paused > live.';
COMMENT ON TABLE hephaestus.migration_log IS
    'Idempotency log for db/connection.py migrate().';
