-- db/migrations/000_initial.sql
-- Migration 000: the initial migration (DL-1, #95).
--
-- This migration is the one that creates hephaestus.control_state and
-- hephaestus.migration_log. It is registered in db/connection.py:migrate()
-- with migration_id "000_initial".
--
-- Apply by running:
--   python3 -m db.connection migrate
-- (or via the project Makefile target `db-migrate` once added).

\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS hephaestus;

CREATE TABLE IF NOT EXISTS hephaestus.control_state (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    mode            TEXT NOT NULL CHECK (mode IN ('live', 'paused', 'frozen', 'killed')),
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_observed_by TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO hephaestus.control_state (id, mode, last_observed_by)
VALUES (1, 'live', 'db/migrations/000_initial.sql')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS hephaestus.migration_log (
    migration_id   TEXT PRIMARY KEY,
    applied_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_by     TEXT NOT NULL,
    checksum       TEXT NOT NULL
);
