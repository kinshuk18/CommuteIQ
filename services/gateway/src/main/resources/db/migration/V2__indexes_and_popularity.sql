-- V2: Additional indexes useful for the proximity query and popular routes
-- The haversine bbox query in gateway uses stop_lat/stop_lon range scans;
-- a composite index gives the planner a tighter scan than two separate indexes.

CREATE INDEX idx_stop_lat_lon_agency ON stop (stop_lat, stop_lon, agency);

-- Aggregate: route popularity will be maintained via Redis ZSET (popular_routes)
-- but we keep a lightweight DB count for cold-start / offline analytics.
CREATE TABLE route_popularity (
    route_fk        BIGINT  PRIMARY KEY REFERENCES route(id) ON DELETE CASCADE,
    plan_count      BIGINT  NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
