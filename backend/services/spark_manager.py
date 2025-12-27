import subprocess
import os
import json
import uuid
import logging
import sys

from services.storage import STORAGE_PATH, get_file_path

JOB_SCRIPTS = {
    "stats": "jobs/stats_job.py",
    "ml": "jobs/ml_job.py",
}


class SparkManager:
    JOBS = {}  # Class attribute to store all jobs
    logger = logging.getLogger("spark_manager")

    if not logger.handlers:
        ch = logging.StreamHandler(stream=sys.stderr)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    logger.setLevel(logging.DEBUG)

    @staticmethod
    def submit_job(job_type: str, filename: str, params: dict = None):
        if params is None:
            params = {}

        job_id = str(uuid.uuid4())
        script_rel = JOB_SCRIPTS.get(job_type)
        if not script_rel:
            raise ValueError(f"Unknown job type: {job_type}")

        os.makedirs(STORAGE_PATH, exist_ok=True)

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../backend
        script_path = os.path.join(backend_dir, script_rel)

        input_path = get_file_path(filename)  # /tmp/storage/<filename>
        output_path = os.path.join(STORAGE_PATH, f"{job_id}_results.json")
        log_path = os.path.join(STORAGE_PATH, f"{job_id}.log")

        python_cmd = ["python"] if os.name == "nt" else ["python3"]

        args = [
            *python_cmd,
            script_path,
            "--input", input_path,
            "--output", output_path,
        ]

        if job_type == "ml":
            # Write params to a file to avoid issues with quoting JSON on Windows
            params_path = os.path.join(STORAGE_PATH, f"{job_id}_params.json")
            params_json = json.dumps(params)
            with open(params_path, "w", encoding="utf-8") as pf:
                pf.write(params_json)

            SparkManager.logger.info("Wrote params file for job_id=%s -> %s", job_id, params_path)
            SparkManager.logger.debug("Params content: %s", params_json)
            args += ["--params-file", params_path]

        try:
            with open(log_path, "w", encoding="utf-8") as log_f:
                process = subprocess.Popen(args, stdout=log_f, stderr=log_f)

            SparkManager.JOBS[job_id] = {
                "status": "RUNNING",
                "process": process,
                "output_path": output_path,
                "log_path": log_path,
                "type": job_type,
            }
            return job_id

        except Exception:
            SparkManager.logger.exception("Failed to submit job")
            raise

    @staticmethod
    def get_job_status(job_id: str):
        job = SparkManager.JOBS.get(job_id)

        os.makedirs(STORAGE_PATH, exist_ok=True)
        fallback_path = os.path.join(STORAGE_PATH, f"{job_id}_results.json")

        if not job:
            if os.path.exists(fallback_path):
                SparkManager.logger.info(
                    "Fallback: results file found for job_id=%s -> %s; treating as COMPLETED",
                    job_id,
                    fallback_path,
                )
                return "COMPLETED"
            return None

        proc = job["process"]
        if proc.poll() is None:
            job["status"] = "RUNNING"
        else:
            job["status"] = "COMPLETED" if proc.returncode == 0 else "FAILED"

            if job["status"] == "COMPLETED":
                out = job.get("output_path", "")
                if not os.path.exists(out) and os.path.exists(fallback_path):
                    SparkManager.logger.info(
                        "Process completed but output missing; using fallback results for job_id=%s -> %s",
                        job_id,
                        fallback_path,
                    )
                    job["output_path"] = fallback_path

        return job["status"]

    @staticmethod
    def get_job_result(job_id: str):
        job = SparkManager.JOBS.get(job_id)

        os.makedirs(STORAGE_PATH, exist_ok=True)
        fallback_path = os.path.join(STORAGE_PATH, f"{job_id}_results.json")

        if not job:
            if os.path.exists(fallback_path):
                SparkManager.logger.info(
                    "Reading job results from fallback file for job_id=%s -> %s",
                    job_id,
                    fallback_path,
                )
                with open(fallback_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None

        SparkManager.get_job_status(job_id)
        if job["status"] != "COMPLETED":
            return None

        output_path = job["output_path"]
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return None
