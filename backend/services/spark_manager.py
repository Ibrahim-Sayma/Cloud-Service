import subprocess
import os
import json
import uuid
import logging
import sys
from typing import Optional

from services.storage import STORAGE_PATH, get_file_path, ensure_storage_dir

JOB_SCRIPTS = {
    "stats": "jobs/stats_job.py",
    "ml": "jobs/ml_job.py",
}

class SparkManager:
    JOBS = {}
    logger = logging.getLogger("spark_manager")

    if not logger.handlers:
        ch = logging.StreamHandler(stream=sys.stderr)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)

    @staticmethod
    def _project_root() -> str:
        # spark_manager.py is in backend/services -> project root is backend
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/

    @staticmethod
    def _script_path(job_type: str) -> str:
        script_rel = JOB_SCRIPTS.get(job_type)
        if not script_rel:
            raise ValueError(f"Unknown job type: {job_type}")

        backend_dir = SparkManager._project_root()  # backend/
        script_path = os.path.join(backend_dir, script_rel)  # backend/jobs/...
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Job script not found: {script_path}")
        return script_path

    @staticmethod
    def submit_job(job_type: str, filename: str, params: Optional[dict] = None):
        params = params or {}
        job_id = str(uuid.uuid4())

        ensure_storage_dir()

        input_path = get_file_path(filename)
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input CSV not found: {input_path}")

        output_path = get_file_path(f"{job_id}_results.json")
        log_path = get_file_path(f"{job_id}.log")

        script_path = SparkManager._script_path(job_type)

        # Use same python running the API (best for DO)
        python_exec = sys.executable

        args = [
            python_exec,
            script_path,
            "--input", input_path,
            "--output", output_path,
        ]

        if job_type == "ml":
            params_path = get_file_path(f"{job_id}_params.json")
            with open(params_path, "w", encoding="utf-8") as pf:
                json.dump(params, pf)
            args += ["--params-file", params_path]

        SparkManager.logger.info("Launching job_id=%s type=%s", job_id, job_type)
        SparkManager.logger.debug("CMD: %s", " ".join(args))
        SparkManager.logger.debug("LOG: %s", log_path)

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
            SparkManager.logger.exception("Failed to submit job_id=%s", job_id)
            raise

    @staticmethod
    def get_job_status(job_id: str):
        ensure_storage_dir()
        job = SparkManager.JOBS.get(job_id)

        fallback_path = get_file_path(f"{job_id}_results.json")

        if not job:
            if os.path.exists(fallback_path):
                return "COMPLETED"
            return None

        proc = job["process"]
        if proc.poll() is None:
            job["status"] = "RUNNING"
        else:
            job["status"] = "COMPLETED" if proc.returncode == 0 else "FAILED"

        return job["status"]

    @staticmethod
    def get_job_result(job_id: str):
        ensure_storage_dir()
        job = SparkManager.JOBS.get(job_id)

        fallback_path = get_file_path(f"{job_id}_results.json")

        if not job:
            if os.path.exists(fallback_path):
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
