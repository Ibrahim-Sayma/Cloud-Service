import os
import re
import json
import subprocess
import time
from pathlib import Path
import pytest

# Integration tests are expensive / require spark. Enable by setting RUN_INTEGRATION=1
pytestmark = pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="Integration tests disabled. Set RUN_INTEGRATION=1 to enable.")

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "run_all_algos.ps1"
STORAGE = ROOT / "storage"


def _run_script_and_capture():
    assert SCRIPTS.exists(), f"Missing script: {SCRIPTS}"
    proc = subprocess.run([
        "powershell", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPTS)
    ], cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    return proc.returncode, proc.stdout, proc.stderr


def test_run_all_algos_and_result_files():
    rc, out, err = _run_script_and_capture()
    assert rc == 0, f"Batch script failed with rc={rc}, stderr={err}"

    # Parse submitted job ids from output
    job_ids = re.findall(r"Submitted job_id: ([0-9a-f\-]+)", out)
    assert job_ids, "No job ids were submitted by the batch script"

    # For each job_id wait for a results file and assert basic keys
    for jid in job_ids:
        res_file = STORAGE / f"{jid}_results.json"
        found = False
        for _ in range(90):  # up to ~3 minutes
            if res_file.exists():
                with open(res_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Basic sanity checks: result should be a dict and include at least one known key
                assert isinstance(data, dict)
                assert any(k in data for k in ("algorithm", "accuracy", "frequent_items", "cluster_centers", "feature_cols")), (
                    f"Result for {jid} missing expected keys: {list(data.keys())}"
                )
                found = True
                break
            time.sleep(2)

        assert found, f"Result file for job {jid} was not found within timeout"
