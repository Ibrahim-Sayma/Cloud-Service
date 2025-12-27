import argparse
import json

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import RegressionEvaluator, BinaryClassificationEvaluator


def _normalize_algo(algo: str) -> str:
    if not algo:
        return "linear_regression"
    a = str(algo).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "linearregression": "linear_regression",
        "linear_regression": "linear_regression",
        "logisticregression": "logistic_regression",
        "logistic_regression": "logistic_regression",
    }
    return aliases.get(a, a)


def _get_first(params: dict, keys, default=None):
    for k in keys:
        if k in params and params[k] not in (None, ""):
            return params[k]
    return default


def save_results(data: dict, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _is_numeric_type(dtype_str: str) -> bool:
    ds = dtype_str.lower()
    return any(x in ds for x in ["int", "bigint", "double", "float", "decimal", "long", "short"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--params", required=False, default=None)
    parser.add_argument("--params-file", required=False, default=None)

    # اختياري: لو بتشغل محلي
    parser.add_argument("--master", required=False, default=None)
    parser.add_argument("--app-name", required=False, default="ml_job_pyspark")
    args = parser.parse_args()

    params = {}
    try:
        if args.params:
            params = json.loads(args.params)
        elif args.params_file:
            with open(args.params_file, "r", encoding="utf-8") as pf:
                params = json.load(pf)
    except Exception:
        params = {}

    algo = _normalize_algo(_get_first(params, ["algorithm", "algo"], "linear_regression"))
    target_col = _get_first(params, ["target_col", "targetColumn", "target_column", "label", "target"], None)
    feature_cols = _get_first(params, ["feature_cols", "featureCols", "feature_columns", "features"], None)

    spark_builder = SparkSession.builder.appName(args.app_name)
    if args.master:
        spark_builder = spark_builder.master(args.master)
    spark = spark_builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    result_data = {"algorithm": algo}

    try:
        # اقرأ CSV
        df = (spark.read
              .option("header", True)
              .option("inferSchema", True)
              .csv(args.input))

        if df is None or len(df.columns) == 0:
            save_results({"error": "Empty dataset"}, args.output)
            return

        # feature_cols ممكن تيجي string
        if isinstance(feature_cols, str):
            feature_cols = [c.strip() for c in feature_cols.split(",") if c.strip()]

        # Auto-select numeric features if not specified
        if not feature_cols:
            numeric_cols = [name for (name, dtype) in df.dtypes if _is_numeric_type(dtype)]
            feature_cols = [c for c in numeric_cols if c != target_col]

        if not feature_cols:
            save_results({"error": "No numeric feature columns found."}, args.output)
            return

        # validate features exist
        missing_features = [c for c in feature_cols if c not in df.columns]
        if missing_features:
            save_results({"error": f"Feature columns not found: {missing_features}"}, args.output)
            return

        # target validation for supported algos
        if algo in ["linear_regression", "logistic_regression"]:
            if not target_col:
                save_results({"error": "target_col is required for this algorithm."}, args.output)
                return
            if target_col not in df.columns:
                save_results({"error": f"Target column '{target_col}' not found."}, args.output)
                return

        # Drop nulls من الأعمدة المهمة (بديل dropna)
        needed_cols = feature_cols + ([target_col] if target_col else [])
        df = df.dropna(subset=needed_cols)

        # كاست الفيتشرز ل double لتفادي مشاكل schema
        for c in feature_cols:
            df = df.withColumn(c, F.col(c).cast("double"))

        # تجهيز label حسب الخوارزمية
        if algo == "linear_regression":
            df = df.withColumn("label", F.col(target_col).cast("double"))
        elif algo == "logistic_regression":
            # لو target سترينغ/كاتيجوري: حوّله لـ 0/1 بشكل بسيط (مناسب للـ binary)
            # 1) لو numeric already: cast double ثم int
            # 2) لو string: encode (أول قيمة -> 0، الباقي -> 1) كحل عملي سريع
            t_dtype = dict(df.dtypes).get(target_col, "").lower()
            if _is_numeric_type(t_dtype):
                df = df.withColumn("label", F.col(target_col).cast("int"))
            else:
                distinct_vals = [r[0] for r in df.select(target_col).distinct().limit(3).collect()]
                if len(distinct_vals) == 0:
                    save_results({"error": "Empty target values."}, args.output)
                    return
                if len(distinct_vals) > 2:
                    save_results({"error": f"Logistic Regression requires binary target. Got >2 distinct values."}, args.output)
                    return
                zero_val = distinct_vals[0]
                df = df.withColumn("label", F.when(F.col(target_col) == F.lit(zero_val), F.lit(0)).otherwise(F.lit(1)))

            # تأكيد binary
            n_classes = df.select("label").distinct().count()
            if n_classes > 2:
                save_results({"error": f"Logistic Regression requires binary target. Got {n_classes} classes."}, args.output)
                return
        else:
            save_results({"error": f"Unsupported algorithm in local mode: {algo}"}, args.output)
            return

        # VectorAssembler
        assembler = VectorAssembler(inputCols=feature_cols, outputCol="features", handleInvalid="skip")
        data = assembler.transform(df).select("features", "label")

        # Split
        train_df, test_df = data.randomSplit([0.8, 0.2], seed=42)

        if algo == "linear_regression":
            model = LinearRegression(featuresCol="features", labelCol="label")
            fitted = model.fit(train_df)
            preds = fitted.transform(test_df)

            rmse = RegressionEvaluator(labelCol="label", predictionCol="prediction", metricName="rmse").evaluate(preds)
            r2 = RegressionEvaluator(labelCol="label", predictionCol="prediction", metricName="r2").evaluate(preds)

            result_data.update({
                "rmse": float(rmse),
                "r2": float(r2),
                "coefficients": [float(v) for v in fitted.coefficients],
                "intercept": float(fitted.intercept),
                "feature_cols": feature_cols,
                "target_col": target_col,
            })

        elif algo == "logistic_regression":
            model = LogisticRegression(featuresCol="features", labelCol="label", maxIter=1000)
            fitted = model.fit(train_df)
            preds = fitted.transform(test_df)

            # ROC AUC
            auc = BinaryClassificationEvaluator(
                labelCol="label",
                rawPredictionCol="rawPrediction",
                metricName="areaUnderROC"
            ).evaluate(preds)

            # Accuracy
            acc = preds.select(
                (F.col("label") == F.col("prediction")).cast("int").alias("ok")
            ).agg(F.avg("ok").alias("acc")).first()["acc"]

            result_data.update({
                "accuracy": float(acc),
                "areaUnderROC": float(auc),
                "feature_cols": feature_cols,
                "target_col": target_col,
            })

        save_results(result_data, args.output)

    except Exception as e:
        save_results({"error": str(e)}, args.output)
    finally:
        try:
            spark.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
