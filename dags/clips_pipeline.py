from datetime import datetime, timedelta

from airflow.decorators import dag, task

default_args = {"retries": 2, "retry_delay": timedelta(minutes=5)}


@dag(
    dag_id="clips_pipeline",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["tiktok", "pyspark", "claude"],
)
def clips_pipeline():
    @task
    def ingest():
        from clips.ingest import ingest_new_videos
        return ingest_new_videos()

    @task
    def transcribe(_):
        from clips.transcribe import transcribe_pending
        return transcribe_pending()

    @task
    def score(_):
        from clips.scoring import score_pending
        return score_pending()

    @task
    def cut(_):
        from clips.editor import cut_pending
        return cut_pending()

    # Fase 2: publish_to_tiktok() y collect_metrics()
    cut(score(transcribe(ingest())))


clips_pipeline()
