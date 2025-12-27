import argparse
import sys
import json
# Import utils first so Windows socketserver compatibility fix runs before pyspark imports
from utils import get_spark_session, read_data, save_results
from pyspark.sql import functions as F

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--params", default="{}")
    args = parser.parse_args()

    spark = get_spark_session("DescriptiveStatistics")
    
    try:
        df = read_data(spark, args.input)
        
        # 1. Row Count
        row_count = df.count()
        
        # 2. Column Count
        col_count = len(df.columns)
        
        # 3. Column Types
        col_types = {name: str(dtype) for name, dtype in df.dtypes}
        
        # 4. Null Counts (isnan only on numeric types)
        dtype_map = {name: str(dtype).lower() for name, dtype in df.dtypes}
        null_counts = {}
        for c in df.columns:
            t = dtype_map.get(c, "")
            if t.startswith(("int", "bigint", "double", "float", "decimal", "long", "smallint")):
                # numeric column: count both null and NaN
                null_counts[c] = df.filter(F.col(c).isNull() | F.isnan(c)).count()
            else:
                # non-numeric: only check for null
                null_counts[c] = df.filter(F.col(c).isNull()).count()
        
        # 5. Basic Stats (Min, Max, Mean) for numeric columns
        numeric_cols = [c for c, t in df.dtypes if t.lower().startswith(("int", "bigint", "double", "float", "decimal", "long", "smallint"))]
        stats = {}
        if numeric_cols:
            desc = df.select(numeric_cols).summary("min", "max", "mean")
            # Collect to driver
            rows = desc.collect()
            # Parse into dictionary
            for row in rows:
                summary_type = row['summary']
                for col in numeric_cols:
                    if col not in stats:
                        stats[col] = {}
                    stats[col][summary_type] = row[col]

        results = {
            "rows": row_count,
            "columns": col_count,
            "column_types": col_types,
            "null_counts": null_counts,
            "statistics": stats
        }
        
        save_results(results, args.output)
    except Exception as e:
        # Save error to results so UI can show it and for post-mortem
        save_results({"error": str(e)}, args.output)
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
