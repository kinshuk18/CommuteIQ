-- V1: GTFS core tables + agency tag
-- stop, route, trip, stop_time plus office, saved_commute, feedback

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── stops ──────────────────────────────────────────────────────────────────
CREATE TABLE stop (
    id          BIGSERIAL PRIMARY KEY,
    agency      TEXT        NOT NULL,           -- 'bmtc' | 'bmrcl'
    stop_id     TEXT        NOT NULL,
    stop_code   TEXT,
    stop_name   TEXT        NOT NULL,
    stop_lat    DOUBLE PRECISION NOT NULL,
    stop_lon    DOUBLE PRECISION NOT NULL,
    location_type   SMALLINT DEFAULT 0,
    parent_station  TEXT,
    UNIQUE (agency, stop_id)
);

CREATE INDEX idx_stop_name_trgm  ON stop USING GIN (stop_name gin_trgm_ops);
CREATE INDEX idx_stop_lat_lon    ON stop (stop_lat, stop_lon);
CREATE INDEX idx_stop_agency     ON stop (agency);

-- ── routes ─────────────────────────────────────────────────────────────────
CREATE TABLE route (
    id          BIGSERIAL PRIMARY KEY,
    agency      TEXT        NOT NULL,
    route_id    TEXT        NOT NULL,
    route_short_name TEXT,
    route_long_name  TEXT,
    route_type  SMALLINT    NOT NULL,   -- 3=bus, 1=metro
    UNIQUE (agency, route_id)
);

CREATE INDEX idx_route_agency    ON route (agency);
CREATE INDEX idx_route_type      ON route (route_type);

-- ── trips ──────────────────────────────────────────────────────────────────
CREATE TABLE trip (
    id          BIGSERIAL PRIMARY KEY,
    agency      TEXT        NOT NULL,
    trip_id     TEXT        NOT NULL,
    route_fk    BIGINT      NOT NULL REFERENCES route(id) ON DELETE CASCADE,
    service_id  TEXT        NOT NULL,
    direction_id SMALLINT,
    shape_id    TEXT,
    UNIQUE (agency, trip_id)
);

CREATE INDEX idx_trip_route_fk   ON trip (route_fk);
CREATE INDEX idx_trip_agency     ON trip (agency);

-- ── stop_times ─────────────────────────────────────────────────────────────
-- Arrival/departure stored as seconds-since-midnight (handles >24h values)
CREATE TABLE stop_time (
    id              BIGSERIAL PRIMARY KEY,
    trip_fk         BIGINT      NOT NULL REFERENCES trip(id) ON DELETE CASCADE,
    stop_fk         BIGINT      NOT NULL REFERENCES stop(id) ON DELETE CASCADE,
    stop_sequence   INT         NOT NULL,
    arrival_sec     INT         NOT NULL,   -- seconds since midnight
    departure_sec   INT         NOT NULL,
    pickup_type     SMALLINT    DEFAULT 0,
    drop_off_type   SMALLINT    DEFAULT 0
);

CREATE INDEX idx_st_trip_fk      ON stop_time (trip_fk);
CREATE INDEX idx_st_stop_fk      ON stop_time (stop_fk);
CREATE INDEX idx_st_departure    ON stop_time (departure_sec);

-- ── offices (OSM POIs) ─────────────────────────────────────────────────────
CREATE TABLE office (
    id          BIGSERIAL PRIMARY KEY,
    osm_id      BIGINT      UNIQUE NOT NULL,
    name        TEXT        NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    office_type TEXT,       -- 'office', 'building', 'landuse', etc.
    tags        JSONB       DEFAULT '{}'
);

CREATE INDEX idx_office_name_trgm ON office USING GIN (name gin_trgm_ops);
CREATE INDEX idx_office_lat_lon   ON office (lat, lon);

-- ── saved_commute ──────────────────────────────────────────────────────────
CREATE TABLE saved_commute (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT        NOT NULL,
    origin_name     TEXT        NOT NULL,
    origin_lat      DOUBLE PRECISION NOT NULL,
    origin_lon      DOUBLE PRECISION NOT NULL,
    dest_name       TEXT        NOT NULL,
    dest_lat        DOUBLE PRECISION NOT NULL,
    dest_lon        DOUBLE PRECISION NOT NULL,
    plan_json       JSONB       NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sc_session_id   ON saved_commute (session_id);

-- ── feedback ───────────────────────────────────────────────────────────────
CREATE TABLE feedback (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT        NOT NULL,
    commute_fk      BIGINT      REFERENCES saved_commute(id),
    rating          SMALLINT    CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fb_session_id   ON feedback (session_id);
CREATE INDEX idx_fb_rating       ON feedback (rating);
