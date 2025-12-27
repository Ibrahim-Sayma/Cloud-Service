import argparse
import json
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import mean_squared_error, r2_score, accuracy_score, roc_auc_score


def _normalize_algo(algo: str) -> str:
    if not algo:
        return "linear_regression"
    a = str(algo).strip().lower()
    a = a.replace(" ", "_").replace("-", "_")
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--params", required=False, default=None)
    parser.add_argument("--params-file", required=False, default=None)
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

    print(f"DEBUG: Loaded params: {params}")

    algo = _normalize_algo(_get_first(params, ["algorithm", "algo"], "linear_regression"))
    target_col = _get_first(params, ["target_col", "targetColumn", "target_column", "label", "target"], None)
    feature_cols = _get_first(params, ["feature_cols", "featureCols", "feature_columns", "features"], None)

    try:
        df = pd.read_csv(args.input).dropna()
        result_data = {"algorithm": algo}

        if df is None or df.shape[1] == 0:
            save_results({"error": "Empty dataset"}, args.output)
            return

        # feature_cols ممكن تيجي string
        if isinstance(feature_cols, str):
            feature_cols = [c.strip() for c in feature_cols.split(",") if c.strip()]

        # Auto-select numeric features if not specified
        if not feature_cols:
            numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            feature_cols = [c for c in numeric_cols if c != target_col]

        if not feature_cols:
            save_results({"error": "No numeric feature columns found."}, args.output)
            return

        # validate features exist
        missing_features = [c for c in feature_cols if c not in df.columns]
        if missing_features:
            save_results({"error": f"Feature columns not found: {missing_features}"}, args.output)
            return

        # LR/LogReg require target
        if algo in ["linear_regression", "logistic_regression"]:
            if not target_col:
                save_results({"error": "target_col is required for this algorithm."}, args.output)
                return
            if target_col not in df.columns:
                save_results({"error": f"Target column '{target_col}' not found."}, args.output)
                return

        X = df[feature_cols]

        if algo == "linear_regression":
            y = pd.to_numeric(df[target_col], errors="coerce")
            valid = y.notna()
            X2 = X[valid]
            y2 = y[valid]

            X_train, X_test, y_train, y_test = train_test_split(X2, y2, test_size=0.2, random_state=42)
            model = LinearRegression()
            model.fit(X_train, y_train)
            preds = model.predict(X_test)

            result_data.update({
                "rmse": float(mean_squared_error(y_test, preds) ** 0.5),
                "r2": float(r2_score(y_test, preds)),
                "coefficients": [float(v) for v in model.coef_],
                "intercept": float(model.intercept_),
                "feature_cols": feature_cols,
                "target_col": target_col,
            })

        elif algo == "logistic_regression":
            y = df[target_col]
            # لو string -> حوله لفئات
            if y.dtype == "object":
                y = y.astype("category").cat.codes

            # لازم binary
            if pd.Series(y).nunique() > 2:
                save_results({"error": f"Logistic Regression requires binary target. Got {pd.Series(y).nunique()} classes."}, args.output)
                return

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            model = LogisticRegression(max_iter=1000)
            model.fit(X_train, y_train)

            pred = model.predict(X_test)
            proba = model.predict_proba(X_test)[:, 1]

            result_data.update({
                "accuracy": float(accuracy_score(y_test, pred)),
                "areaUnderROC": float(roc_auc_score(y_test, proba)),
                "feature_cols": feature_cols,
                "target_col": target_col,
            })

        else:
            result_data["error"] = f"Unsupported algorithm in local mode: {algo}"

        save_results(result_data, args.output)

    except Exception as e:
        save_results({"error": str(e)}, args.output)


if __name__ == "__main__":
    main()
