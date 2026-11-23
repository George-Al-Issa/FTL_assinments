CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS fields (
    id uuid PRIMARY KEY,
    location geometry(Point, 4326) NOT NULL,
    area_ha double precision NOT NULL CHECK (area_ha > 0 AND area_ha < 'Infinity'),
    irrigation text NOT NULL CHECK (irrigation IN ('unknown', 'rainfed', 'irrigated')),
    captured_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS fields_location_gix ON fields USING gist (location);
