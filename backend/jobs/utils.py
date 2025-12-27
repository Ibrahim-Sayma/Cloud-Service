# Windows PySpark Compatibility Fix
import sys
import os

# Fix UnixStreamServer AttributeError on Windows
if os.name == 'nt':  # Windows
    import socketserver
    if not hasattr(socketserver, 'UnixStreamServer'):
        # Create dummy class to prevent AttributeError
        class UnixStreamServer:
            pass
        socketserver.UnixStreamServer = UnixStreamServer

from pyspark.sql import SparkSession

def get_spark_session(app_name):
    return SparkSession.builder \
        .appName(app_name) \
        .getOrCreate()

def read_data(spark, file_path):
    # Support CSV and JSON based on extension
    if file_path.endswith('.csv'):
        return spark.read.csv(file_path, header=True, inferSchema=True)
    elif file_path.endswith('.json'):
        return spark.read.json(file_path)
    else:
        # Fallback to text
        return spark.read.text(file_path)

def save_results(data, output_path):
    # Data should be a dictionary
    import json
    with open(output_path, 'w') as f:
        json.dump(data, f)
