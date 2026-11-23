CREATE TABLE IF NOT EXISTS plantings (
    id uuid PRIMARY KEY,
    customer text NOT NULL,
    crop text NOT NULL,
    planted_on date NOT NULL,
    location geometry(Point, 4326) NOT NULL,
    area_ha double precision NOT NULL CHECK (area_ha > 0 AND area_ha < 'Infinity'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS plantings_customer_idx ON plantings (customer, created_at DESC);
CREATE INDEX IF NOT EXISTS plantings_created_idx ON plantings (created_at DESC);
CREATE INDEX IF NOT EXISTS plantings_location_gix ON plantings USING gist (location);
