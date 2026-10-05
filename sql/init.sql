CREATE DATABASE clips;
\c clips

CREATE TABLE videos (
    id          SERIAL PRIMARY KEY,
    source_url  TEXT UNIQUE NOT NULL,
    title       TEXT,
    local_path  TEXT,
    status      TEXT NOT NULL DEFAULT 'downloaded',  -- downloaded -> transcribed -> scored
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE segments (
    id           SERIAL PRIMARY KEY,
    video_id     INT NOT NULL REFERENCES videos(id),
    start_s      DOUBLE PRECISION NOT NULL,
    end_s        DOUBLE PRECISION NOT NULL,
    text         TEXT NOT NULL,
    rule_score   DOUBLE PRECISION,
    claude_score DOUBLE PRECISION,
    final_score  DOUBLE PRECISION,
    title        TEXT,
    hook         TEXT,
    hashtags     TEXT[],
    selected     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE clips (
    id             SERIAL PRIMARY KEY,
    segment_id     INT NOT NULL UNIQUE REFERENCES segments(id),
    file_path      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'rendered',  -- rendered -> published
    tiktok_post_id TEXT,
    published_at   TIMESTAMPTZ
);

CREATE TABLE clip_metrics (
    clip_id        INT NOT NULL REFERENCES clips(id),
    captured_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    views          BIGINT,
    likes          BIGINT,
    shares         BIGINT,
    avg_watch_time DOUBLE PRECISION,
    PRIMARY KEY (clip_id, captured_at)
);

CREATE TABLE llm_calls (
    id            SERIAL PRIMARY KEY,
    task          TEXT NOT NULL,
    model         TEXT NOT NULL,
    input_tokens  INT,
    output_tokens INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
