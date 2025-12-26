import os
import sys
import json
import uuid
# Ensure backend is on sys.path so we can import the application's modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from services.spark_manager import SparkManager

storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage"))
job_id = str(uuid.uuid4())

# Create a fake results file
results = {
    "rows": 3,
    "columns": 3,
    "column_types": {"name": "string", "age": "int", "salary": "int"},
    "null_counts": {"name": 0, "age": 0, "salary": 0},
    "statistics": {"age": {"min": 23, "max": 30, "mean": 26.6667}, "salary": {"min": 500, "max": 800, "mean": 650.0}}
}

results_path = os.path.join(storage_dir, f"{job_id}_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f)

# Create a fake log file
log_path = os.path.join(storage_dir, f"{job_id}.log")
with open(log_path, "w", encoding="utf-8") as f:
    f.write("SIMULATION: created fake results\n")

# Create a dummy process object to simulate completed process
class DummyProc:
    def poll(self):
        return 1
    @property
    def returncode(self):
        return 0

# Register job in SparkManager.JOBS
SparkManager.JOBS[job_id] = {
    "status": "COMPLETED",
    "process": DummyProc(),
    "output_path": results_path,
    "log_path": log_path,
    "type": "stats",
}

print("Simulated job_id:", job_id)
print("get_job_status ->", SparkManager.get_job_status(job_id))
print("get_job_result ->", SparkManager.get_job_result(job_id))

# Now simulate server restart: remove job from JOBS and test fallback
SparkManager.JOBS.pop(job_id, None)
print("After removing from JOBS:")
print("get_job_status (fallback) ->", SparkManager.get_job_status(job_id))
print("get_job_result (fallback) ->", SparkManager.get_job_result(job_id))
