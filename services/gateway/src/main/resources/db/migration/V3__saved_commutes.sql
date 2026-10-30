-- V3: saved commutes and feedback tables for user persistence
-- These are application-side tables (not GTFS); DDL owned by Flyway.

CREATE TABLE IF NOT EXISTS saved_commutes (
    id             BIGSERIAL PRIMARY KEY,
    user_id        VARCHAR(128) NOT NULL,
    origin_stop_id VARCHAR(64),
    dest_stop_id   VARCHAR(64),
    label          VARCHAR(255),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_saved_commutes_user ON saved_commutes (user_id, created_at DESC);
