from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, root_validator
from typing import Any, Dict, Literal, Optional
import json
import logging

from services.spark_manager import SparkManager
from services.storage import file_exists

router = APIRouter(prefix="/jobs", tags=["Jobs"])
logger = logging.getLogger("jobs")


def normalize_algorithm(value: Optional[str]) -> str:
    """
    Accepts values like:
      - "Linear Regression", "linear_regression", "LinearRegression"
      - "Logistic Regression", "logistic_regression"
    and returns a snake_case key used by ml_job.py
    """
    if not value:
        return "linear_regression"

    v = str(value).strip().lower()

    # common UI labels -> internal keys
    mapping = {
        "linear regression": "linear_regression",
        "linear_regression": "linear_regression",
        "linearregression": "linear_regression",

        "logistic regression": "logistic_regression",
        "logistic_regression": "logistic_regression",
        "logisticregression": "logistic_regression",

        "kmeans": "kmeans",
        "k-means": "kmeans",

        "fpgrowth": "fpgrowth",
        "fp-growth": "fpgrowth",
    }

    return mapping.get(v, v.replace(" ", "_"))


class JobRequest(BaseModel):
    filename: str
    job_type: Literal["stats", "ml"]
    params: Dict[str, Any] = Field(default_factory=dict)

    @root_validator(pre=True)
    def parse_and_normalize_params(cls, values):
        params = values.get("params")

        # 1) None -> {}
        if params is None:
            params = {}

        # 2) If params arrives as JSON string -> dict
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                # fallback: keep raw string so we can debug
                params = {"_raw_params": params}

        # 3) Ensure dict
        if not isinstance(params, dict):
            params = {"_raw_params": params}

        # 4) Normalize algorithm key/value for ML
        # accept algo/algorithm
        algo = params.get("algorithm") or params.get("algo")
        params["algorithm"] = normalize_algorithm(algo)

        # 5) Normalize target column name (frontend might send different key)
        # Accept: target_col / targetColumn / target / label / y
        if "target_col" not in params or not params.get("target_col"):
            for k in ["targetColumn", "target", "label", "y"]:
                if params.get(k):
                    params["target_col"] = params.get(k)
                    break

        values["params"] = params
        return values


@router.post("/submit")
def submit_job(request: JobRequest):
    # ✅ file exists?
    if not file_exists(request.filename):
        raise HTTPException(status_code=404, detail="File not found")

    # ✅ useful logs (بتشوفها بالكونسول)
    logger.info("submit_job filename=%s job_type=%s params=%s",
                request.filename, request.job_type, request.params)

    # ✅ Validation حسب نوع الـ ML algorithm
    if request.job_type == "ml":
        algo = request.params.get("algorithm", "linear_regression")

        # algorithms that REQUIRE target_col
        needs_target = algo in {"linear_regression", "logistic_regression"}

        if needs_target and not request.params.get("target_col"):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "target_col is required for this algorithm",
                    "algorithm": algo,
                    "received_params": request.params
                }
            )

        # optional: if feature_cols coming from UI as string "a,b,c"
        fc = request.params.get("feature_cols")
        if isinstance(fc, str):
            request.params["feature_cols"] = [x.strip() for x in fc.split(",") if x.strip()]

    try:
        job_id = SparkManager.submit_job(
            request.job_type,
            request.filename,
            request.params
        )
        return {
            "job_id": job_id,
            "status": "SUBMITTED",
            "received_params": request.params
        }
    except Exception as e:
        logger.exception("submit_job failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
def get_status(job_id: str):
    logger.info(f"🔍 Checking status for job_id: {job_id}")
    logger.info(f"📦 Available jobs: {list(SparkManager.JOBS.keys()) if hasattr(SparkManager, 'JOBS') else 'N/A'}")
    
    status = SparkManager.get_job_status(job_id)
    if not status:
        # If a results file exists on disk, prefer that (handles restarts or late-write races)
        result = SparkManager.get_job_result(job_id)
        if result is not None:
            logger.info(f"Fallback: results present on disk for job_id=%s; returning COMPLETED", job_id)
            return {"job_id": job_id, "status": "COMPLETED", "note": "Found results on disk (fallback)"}

        # Otherwise, return a non-error PENDING status so clients keep polling
        logger.info(f"Job %s not tracked yet; returning PENDING to encourage retry", job_id)
        return {"job_id": job_id, "status": "PENDING"}

    return {"job_id": job_id, "status": status} 


@router.get("/{job_id}/test")
def test_job_endpoint(job_id: str):
    """Test endpoint to verify routing works"""
    return {
        "message": "Routing works! ✅",
        "job_id": job_id,
        "note": "This is a test endpoint"
    }


@router.get("/{job_id}/results")
def get_results(job_id: str):
    result = SparkManager.get_job_result(job_id)

    if result is None:
        status = SparkManager.get_job_status(job_id)

        if status == "FAILED":
            # بدل "Job failed" العامة، خليه يرجع سبب واضح لو موجود
            raise HTTPException(status_code=500, detail="Job failed (check job log in storage)")
        if status == "RUNNING":
            raise HTTPException(status_code=202, detail="Job is still running")

        raise HTTPException(status_code=404, detail="Results not found")

    return result
