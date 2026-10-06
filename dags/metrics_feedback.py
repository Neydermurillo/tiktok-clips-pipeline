from datetime import datetime, timedelta

from airflow.decorators import dag, task

default_args = {"retries": 2, "retry_delay": timedelta(minutes=5)}


@dag(
    dag_id="metrics_feedback",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["tiktok", "pyspark", "feedback"],
)
def metrics_feedback():
    @task
    def collect_metrics():
        from clips.metrics import collect_metrics as run
        return run()

    @task
    def update_weights(_):
        from clips.insights import update_weights as run
        return run()

    update_weights(collect_metrics())


metrics_feedback()
