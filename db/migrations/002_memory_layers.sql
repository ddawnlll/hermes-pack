-- db/migrations/002_memory_layers.sql
-- Migration 002: memory layer tables (DL-4, #98).
--
-- Audit finding: 7 layers were proposed but flagged as too ambitious.
-- v0.6 ships 4 layers (episodic, semantic, scar, precedent) and defers
-- 3 (procedural, narrative, cross-project) to v0.7.
--
-- v0.6 layer table mapping:
--   episodic  -> hephaestus.memory_episodic   (tick log mirror; per-tick events)
--   semantic  -> hephaestus.memory_semantic   (pgvector embeddings; related to candidates)
--   scar      -> hephaestus.memory_scar       (negative patterns: failed candidates)
--   precedent -> hephaestus.precedents         (already in 001_candidates.sql; reference here)
--
-- Procedural / narrative / cross-project are deferred; the migration
-- creates a "deferred" marker table so we can track which layers are
-- promised for v0.7.

\set ON_ERROR_STOP on

-- 1. episodic: tick event log (mirror of tick-journal.py).
CREATE TABLE IF NOT EXISTS hephaestus.memory_episodic (
    id          BIGSERIAL PRIMARY KEY,
    tick_id     BIGINT NOT NULL,
    actor       TEXT NOT NULL,
    kind        TEXT NOT NULL,
    candidate_id UUID,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_episodic_tick ON hephaestus.memory_episodic(tick_id);
CREATE INDEX IF NOT EXISTS idx_memory_episodic_actor_kind ON hephaestus.memory_episodic(actor, kind);
CREATE INDEX IF NOT EXISTS idx_memory_episodic_payload_gin ON hephaestus.memory_episodic USING GIN (payload);

-- 2. semantic: vector search for similar candidates / beliefs.
--    embedding column uses pgvector (extension already created in 000).
--    Dimension: 1536 (matches the BE-6 #84 precedent encoder default).
CREATE TABLE IF NOT EXISTS hephaestus.memory_semantic (
    id            BIGSERIAL PRIMARY KEY,
    source_kind   TEXT NOT NULL CHECK (source_kind IN ('candidate', 'belief', 'hypothesis', 'precedent')),
    source_id     TEXT NOT NULL,
    embedding     vector(1536) NOT NULL,
    model         TEXT NOT NULL DEFAULT 'v0.6-encoder',
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload       JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_memory_semantic_source ON hephaestus.memory_semantic(source_kind, source_id);
CREATE INDEX IF NOT EXISTS idx_memory_semantic_embedding_ivfflat
    ON hephaestus.memory_semantic USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_memory_semantic_payload_gin ON hephaestus.memory_semantic USING GIN (payload);

-- 3. scar: negative patterns (rolled_back / failed / dead candidates,
--    with root-cause tags for "what went wrong"). Used by GA-3 (#127)
--    to compute the regret_rate metric.
CREATE TABLE IF NOT EXISTS hephaestus.memory_scar (
    id             BIGSERIAL PRIMARY KEY,
    tick_id        BIGINT NOT NULL,
    candidate_id   UUID,
    scar_kind      TEXT NOT NULL CHECK (scar_kind IN
                       ('rollback', 'dead', 'shadow_fail', 'canary_fail', 'observation_regression')),
    root_cause     TEXT NOT NULL,
    lesson         TEXT NOT NULL DEFAULT '',
    learned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_memory_scar_tick ON hephaestus.memory_scar(tick_id);
CREATE INDEX IF NOT EXISTS idx_memory_scar_kind ON hephaestus.memory_scar(scar_kind);
CREATE INDEX IF NOT EXISTS idx_memory_scar_payload_gin ON hephaestus.memory_scar USING GIN (payload);

-- 4. precedent: already created in 001_candidates.sql. We add an index
--    that the BE-6 (#84) precedent_query.py uses for fast signature
--    matching.
CREATE INDEX IF NOT EXISTS idx_precedents_situation_signature
    ON hephaestus.precedents ((situation->>'risk'), (situation->>'evidence_pattern'));

-- 5. deferred_layers: marker table for layers promised to v0.7. The
--    migration runner records each deferred layer so v0.7 can pick them
--    up without re-deriving the design.
CREATE TABLE IF NOT EXISTS hephaestus.deferred_layers (
    layer_name   TEXT PRIMARY KEY,
    rationale    TEXT NOT NULL,
    target_version TEXT NOT NULL,
    deferred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO hephaestus.deferred_layers (layer_name, rationale, target_version) VALUES
    ('procedural', 'pattern extraction + retrieval + application is a research project; deferred to v0.7 with a dedicated design doc.', 'v0.7'),
    ('narrative', 'reflector-dispatch.sh + dream-channel.py already cover narrative generation; schema formalization deferred to v0.7.', 'v0.7'),
    ('cross_project', 'cross-project belief movement is an architecture decision (separate workspace or shared store?); deferred to v0.7.', 'v0.7')
ON CONFLICT (layer_name) DO NOTHING;
