-- Fase 3: métricas con origen y pesos de scoring aprendidos.
-- cat sql/migrations/003_phase3.sql | docker compose exec -T postgres psql -U airflow -d clips
ALTER TABLE clip_metrics ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';  -- manual | simulated | tiktok

CREATE TABLE IF NOT EXISTS scoring_weights (
    id          SERIAL PRIMARY KEY,
    w_rule      DOUBLE PRECISION NOT NULL,
    w_ai        DOUBLE PRECISION NOT NULL,
    n_samples   INT NOT NULL,
    corr_rule   DOUBLE PRECISION,
    corr_ai     DOUBLE PRECISION,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
