BEGIN;

CREATE TABLE IF NOT EXISTS dashboard_sessions (
    token_hash text PRIMARY KEY,
    username text NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS dashboard_session_expiry_idx ON dashboard_sessions (expires_at);

CREATE TABLE IF NOT EXISTS provider_settings (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    settings jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    audience text NOT NULL CHECK (audience IN ('admin','customer')),
    recipient text,
    title text NOT NULL,
    message text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_audience_idx ON notifications (audience, id DESC);

CREATE TABLE IF NOT EXISTS notification_reads (
    username text NOT NULL,
    notification_id bigint NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    PRIMARY KEY (username, notification_id)
);

CREATE OR REPLACE FUNCTION crosafe_notify_planting() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO notifications (audience, title, message)
    VALUES ('admin', 'New planting recorded', NEW.customer || ' reported ' || NEW.crop || '.');
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS planting_notifications ON plantings;
CREATE TRIGGER planting_notifications AFTER INSERT ON plantings
FOR EACH ROW EXECUTE FUNCTION crosafe_notify_planting();

COMMIT;
