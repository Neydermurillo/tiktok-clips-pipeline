from clips.config import KEYWORDS


def get_spark():
    from pyspark.sql import SparkSession

    return SparkSession.builder.master("local[*]").appName("clip-scoring").getOrCreate()


def rule_scores(spark, rows: list[dict]) -> dict[int, float]:
    """rows: [{id, text, duration}] -> {id: score 0..100}. Reglas simples y explicables."""
    from pyspark.sql import functions as F

    pattern = "(" + "|".join(KEYWORDS) + ")"
    df = spark.createDataFrame(rows)
    df = (
        df.withColumn("words", F.size(F.split("text", r"\s+")))
        .withColumn("wps", F.col("words") / F.greatest(F.col("duration"), F.lit(1.0)))
        .withColumn("questions", F.regexp_count("text", F.lit(r"\?")))
        .withColumn("exclaims", F.regexp_count("text", F.lit(r"!")))
        .withColumn("kw", F.regexp_count(F.lower("text"), F.lit(pattern)))
        .withColumn(
            "score",
            F.lit(20.0)
            + F.least(F.col("wps") / 3.0, F.lit(1.0)) * 30
            + F.least(F.col("questions"), F.lit(3)) * 5
            + F.least(F.col("exclaims"), F.lit(2)) * 5
            + F.least(F.col("kw"), F.lit(5)) * 5,
        )
        .select("id", "score")
    )
    return {r["id"]: float(r["score"]) for r in df.collect()}
