CREATE TABLE IF NOT EXISTS sensors (
    sensor_id TEXT PRIMARY KEY,
    sensor_name TEXT,
    category TEXT,
    region TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    measurement_unit TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    sensor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    last_sample_timestamp TIMESTAMPTZ NOT NULL,
    peak_frequency DOUBLE PRECISION,
    peak_amplitude DOUBLE PRECISION,
    duration DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_events_sensor_id
    ON events (sensor_id);

CREATE INDEX IF NOT EXISTS idx_events_last_sample_timestamp
    ON events (last_sample_timestamp DESC);
