import argparse
import json

# Import utils first so Windows socketserver compatibility fix runs before pyspark imports
from utils import get_spark_session, read_data, save_results

from pyspark.ml.feature import VectorAssembler, StringIndexer
from pyspark.ml.regression import LinearRegression
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.clustering import KMeans
from pyspark.ml.fpm import FPGrowth
from pyspark.ml.evaluation import MulticlassClassificationEvaluator, BinaryClassificationEvaluator


def _normalize_algo(algo: str) -> str:
    if not algo:
        return "linear_regression"
    a = str(algo).strip().lower()
    a = a.replace(" ", "_").replace("-", "_")
    # دعم خيارات الفرونت
    aliases = {
        "linearregression": "linear_regression",
        "linear_regression": "linear_regression",
        "logisticregression": "logistic_regression",
        "logistic_regression": "logistic_regression",
        "k_means": "kmeans",
        "kmeans": "kmeans",
        "fp_growth": "fpgrowth",
        "fpgrowth": "fpgrowth",
    }
    return aliases.get(a, a)


def _get_first(params: dict, keys, default=None):
    for k in keys:
        if k in params and params[k] not in (None, ""):
            return params[k]
    return default


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    # Support either inline params or a params file (safer on Windows)
    parser.add_argument("--params", required=False, default=None)
    parser.add_argument("--params-file", required=False, default=None)
    args = parser.parse_args()

    # params ممكن تيجي string/JSON او ممكن تكون في ملف
    params = {}
    try:
        if args.params:
            params = json.loads(args.params)
        elif args.params_file:
            with open(args.params_file, "r", encoding="utf-8") as pf:
                params = json.load(pf)
    except Exception:
        params = {}

    # Helpful debug log (goes into the spark job log)
    print(f"DEBUG: Loaded params: {params}")

    algo = _normalize_algo(_get_first(params, ["algorithm", "algo"], "linear_regression"))

    # دعم مفاتيح مختلفة من الفرونت
    target_col = _get_first(params, ["target_col", "targetColumn", "target_column", "label", "target"], None)
    feature_cols = _get_first(params, ["feature_cols", "featureCols", "feature_columns", "features"], None)

    spark = get_spark_session(f"MLJob_{algo}")

    try:
        df = read_data(spark, args.input).dropna()

        result_data = {"algorithm": algo}

        if df is None or len(df.columns) == 0:
            save_results({"error": "Empty dataset"}, args.output)
            return

        # -------------------------
        # Feature Assembly (LR / LogReg / KMeans)
        # -------------------------
        if algo in ["linear_regression", "logistic_regression", "kmeans"]:
            # لو الفرونت بعث feature_cols كـ string "a,b,c"
            if isinstance(feature_cols, str):
                feature_cols = [c.strip() for c in feature_cols.split(",") if c.strip()]

            # Auto-select numeric columns if not specified
            if not feature_cols:
                numeric_cols = [c for c, t in df.dtypes if t.startswith(("int", "bigint", "double", "float", "decimal"))]
                if algo == "kmeans":
                    feature_cols = numeric_cols
                else:
                    # للـ regression/classification استثني الـ target
                    feature_cols = [c for c in numeric_cols if c != target_col]

            if not feature_cols:
                save_results({"error": "No numeric feature columns found to train on."}, args.output)
                return

            # تأكد الأعمدة موجودة
            missing_features = [c for c in feature_cols if c not in df.columns]
            if missing_features:
                save_results({"error": f"Feature columns not found: {missing_features}"}, args.output)
                return

            # للـ LR / LogReg لازم target موجود
            if algo in ["linear_regression", "logistic_regression"]:
                if not target_col:
                    save_results({"error": "target_col is required for this algorithm."}, args.output)
                    return
                if target_col not in df.columns:
                    save_results({"error": f"Target column '{target_col}' not found in dataset."}, args.output)
                    return

            # جهّز label للـ LogisticRegression
            label_col_for_model = target_col  # افتراضي

            if algo == "logistic_regression":
                # إذا label string => StringIndexer
                dtype_map = dict(df.dtypes)
                if dtype_map.get(target_col, "").startswith("string"):
                    indexer = StringIndexer(inputCol=target_col, outputCol="label", handleInvalid="skip")
                    df = indexer.fit(df).transform(df)
                    label_col_for_model = "label"
                else:
                    # خليها double
                    df = df.withColumn(target_col, df[target_col].cast("double"))
                    label_col_for_model = target_col

                # تحقق أنها ثنائية (قيمتين)
                distinct_count = df.select(label_col_for_model).distinct().count()
                if distinct_count > 2:
                    save_results(
                        {
                            "error": (
                                f"Logistic Regression needs a binary target (2 classes). "
                                f"Column '{target_col}' has {distinct_count} distinct values. "
                                f"Use Linear Regression للسعر، أو اعمل target ثنائي (مثلاً high_salary 0/1)."
                            )
                        },
                        args.output,
                    )
                    return

            if algo == "linear_regression":
                df = df.withColumn(target_col, df[target_col].cast("double"))
                label_col_for_model = target_col

            # Sanitize feature list: remove None/empty and ensure strings
            feature_cols = [str(c) for c in feature_cols if c]
            print(f"DEBUG: feature_cols after sanitization: {feature_cols}")
            print(f"DEBUG: df.columns: {df.columns}")
            if not feature_cols:
                save_results({"error": "No valid feature columns provided."}, args.output)
                return

            # cast features to double (أحياناً بتسبب مشاكل إذا كانت int/decimal)
            try:
                for c in feature_cols:
                    df = df.withColumn(c, df[c].cast("double"))
            except Exception as e:
                save_results({"error": f"Failed to cast feature columns to double: {str(e)}"}, args.output)
                return

            try:
                assembler = VectorAssembler(inputCols=feature_cols, outputCol="features", handleInvalid="skip")
                transformed = assembler.transform(df)
                # For KMeans we don't have a label column; only select features
                if label_col_for_model in (None, "", target_col) and algo == "kmeans":
                    data = transformed.select("features")
                else:
                    # include label when present (label might be 'label' or actual target_col)
                    select_cols = ["features"]
                    if label_col_for_model:
                        select_cols.append("label" if label_col_for_model == "label" else label_col_for_model)
                    data = transformed.select(*select_cols)
            except Exception as e:
                save_results({"error": f"Failed to assemble feature vector: {str(e)}"}, args.output)
                return

        # -------------------------
        # Algorithms
        # -------------------------
        if algo == "linear_regression":
            lr = LinearRegression(featuresCol="features", labelCol=target_col)
            model = lr.fit(data)
            summary = model.summary
            result_data.update(
                {
                    "rmse": summary.rootMeanSquaredError,
                    "r2": summary.r2,
                    "coefficients": [float(x) for x in model.coefficients],
                    "intercept": float(model.intercept),
                    "feature_cols": feature_cols,
                    "target_col": target_col,
                }
            )

        elif algo == "logistic_regression":
            # label ممكن يكون "label" أو target_col
            label_col = "label" if "label" in data.columns else target_col

            lr = LogisticRegression(featuresCol="features", labelCol=label_col)
            model = lr.fit(data)

            preds = model.transform(data)

            acc_eval = MulticlassClassificationEvaluator(labelCol=label_col, predictionCol="prediction", metricName="accuracy")
            roc_eval = BinaryClassificationEvaluator(labelCol=label_col, rawPredictionCol="rawPrediction", metricName="areaUnderROC")

            result_data.update(
                {
                    "accuracy": float(acc_eval.evaluate(preds)),
                    "areaUnderROC": float(roc_eval.evaluate(preds)),
                    "feature_cols": feature_cols,
                    "target_col": target_col,
                }
            )

        elif algo == "kmeans":
            k = int(_get_first(params, ["k"], 3))
            kmeans = KMeans(k=k, seed=1, featuresCol="features")
            model = kmeans.fit(data)
            centers = model.clusterCenters()
            result_data.update(
                {
                    "k": k,
                    "cluster_centers": [c.tolist() for c in centers],
                    "feature_cols": feature_cols,
                }
            )

        elif algo == "fpgrowth":
            items_col = _get_first(params, ["items_col", "itemsCol"], df.columns[0])
            minSupport = float(_get_first(params, ["minSupport"], 0.1))
            minConfidence = float(_get_first(params, ["minConfidence"], 0.1))

            if items_col not in df.columns:
                save_results({"error": f"items_col '{items_col}' not found in dataset."}, args.output)
                return

            # If items column is a string, convert to array by splitting on commas
            dtype_map = dict(df.dtypes)
            if dtype_map.get(items_col, "").startswith("string"):
                from pyspark.sql.functions import split, trim, col
                df = df.withColumn(items_col, split(trim(col(items_col)), "\\s*,\\s*"))

            try:
                fp = FPGrowth(itemsCol=items_col, minSupport=minSupport, minConfidence=minConfidence)
                model = fp.fit(df)

                freq_items = model.freqItemsets.limit(10).collect()
                rules = model.associationRules.limit(10).collect()

                result_data.update(
                    {
                        "items_col": items_col,
                        "minSupport": minSupport,
                        "minConfidence": minConfidence,
                        "frequent_items": [row.asDict() for row in freq_items],
                        "association_rules": [row.asDict() for row in rules],
                    }
                )
            except Exception as e:
                save_results({"error": str(e)}, args.output)
                return

        else:
            result_data["error"] = f"Unknown algorithm: {algo}"

        save_results(result_data, args.output)

    except Exception as e:
        save_results({"error": str(e)}, args.output)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
