-- Para instalaciones de la Fase 1 ya creadas:
-- cat sql/migrations/002_phase2.sql | docker compose exec -T postgres psql -U airflow -d clips
CREATE TABLE IF NOT EXISTS transcript_lines (
    id       SERIAL PRIMARY KEY,
    video_id INT NOT NULL REFERENCES videos(id),
    start_s  DOUBLE PRECISION NOT NULL,
    end_s    DOUBLE PRECISION NOT NULL,
    text     TEXT NOT NULL
);
ALTER TABLE clips ADD COLUMN IF NOT EXISTS caption TEXT;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS publish_id TEXT;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS error TEXT;
