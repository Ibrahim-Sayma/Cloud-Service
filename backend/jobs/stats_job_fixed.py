"""
Fixed stats job for Windows - bypasses UnixStreamServer issue
"""
import sys
import os

# Fix for Windows PySpark issue
os.environ['PYSPARK_SUBMIT_ARGS'] = '--master local[*] pyspark-shell'

# Monkey patch to avoid UnixStreamServer
import socketserver
if not hasattr(socketserver, 'UnixStreamServer'):
    class DummyUnixStreamServer:
        pass
    socketserver.UnixStreamServer = DummyUnixStreamServer

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    spark = SparkSession.builder \
        .appName("StatsJob") \
        .master("local[*]") \
        .getOrCreate()

    df = spark.read.csv(args.input, header=True, inferSchema=True)

    # Basic statistics
    numeric_cols = [f.name for f in df.schema.fields if str(f.dataType) in ['IntegerType', 'DoubleType', 'LongType', 'FloatType']]
    
    result = {
        "row_count": df.count(),
        "column_count": len(df.columns),
        "columns": df.columns,
        "sample_data": df.limit(5).toPandas().to_dict(orient='records'),
        "statistics": {}
    }

    if numeric_cols:
        stats_df = df.select(numeric_cols).summary()
        stats_dict = {}
        for col in numeric_cols:
            col_stats = stats_df.select('summary', col).collect()
            stats_dict[col] = {row['summary']: row[col] for row in col_stats}
        result["statistics"] = stats_dict

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    spark.stop()

except Exception as e:
    import traceback
    error_result = {
        "error": str(e),
        "traceback": traceback.format_exc()
    }
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(error_result, f, indent=2)
    sys.exit(1)
