-- =============================================================================
-- Project Atlas — PostgreSQL initialisation
--
-- Executed by the postgres image's entrypoint on FIRST START ONLY, against an
-- empty data volume. It never runs again. Schema changes after that point are
-- migrations, not edits to this file.
--
-- Scope at ATLAS-TASK-0001: extensions and schemas only. No tables — the
-- packages that would own them are empty by design.
-- =============================================================================

-- Deterministic UUID generation for entity identifiers.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Query statistics, needed before there is a performance problem to diagnose.
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- -----------------------------------------------------------------------------
-- Schemas — one per bounded context, so that ownership and grants can be
-- expressed per area rather than across one flat public schema.
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS trading;   -- orders, positions, fills
CREATE SCHEMA IF NOT EXISTS risk;      -- limits, verdicts, exposure state
CREATE SCHEMA IF NOT EXISTS audit;     -- append-only decision record
CREATE SCHEMA IF NOT EXISTS analytics; -- attribution and reporting

COMMENT ON SCHEMA trading   IS 'Order lifecycle and position state.';
COMMENT ON SCHEMA risk      IS 'Risk limits, verdicts and exposure state.';
COMMENT ON SCHEMA audit     IS 'Append-only record of every decision and action.';
COMMENT ON SCHEMA analytics IS 'Derived performance and attribution data.';

-- -----------------------------------------------------------------------------
-- Timestamps are stored as timestamptz throughout. A trading system that stores
-- naive timestamps has a correctness bug waiting on the next DST transition.
-- -----------------------------------------------------------------------------
SET timezone = 'UTC';
