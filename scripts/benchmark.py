import subprocess
import time
import pandas as pd
import matplotlib.pyplot as plt
import os

NODES = [1, 2, 4, 8]
INPUT_FILE = "../storage/benchmark_data.csv"
OUTPUT_DIR = "../storage"
JOB_SCRIPT = "../backend/jobs/stats_job.py"

def run_benchmark():
    results = []
    
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Run generate_data.py first.")
        return

    print(f"Starting benchmark on {INPUT_FILE}...")
    print("-" * 50)
    print(f"{'Nodes':<10} | {'Time (s)':<10} | {'Speedup':<10} | {'Efficiency':<10}")
    print("-" * 50)

    base_time = None

    for n in NODES:
        start_time = time.time()
        
        # Construct spark-submit command with master local[N]
        cmd = [
            "spark-submit",
            "--master", f"local[{n}]",
            JOB_SCRIPT,
            "--input", INPUT_FILE,
            "--output", f"{OUTPUT_DIR}/bench_result_{n}.json"
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print(f"Error running on {n} nodes")
            continue
            
        end_time = time.time()
        duration = end_time - start_time
        
        if n == 1:
            base_time = duration
            speedup = 1.0
            efficiency = 1.0
        else:
            speedup = base_time / duration if base_time else 0
            efficiency = speedup / n

        results.append({
            "Nodes": n,
            "Time": duration,
            "Speedup": speedup,
            "Efficiency": efficiency
        })

        print(f"{n:<10} | {duration:<10.2f} | {speedup:<10.2f} | {efficiency:<10.2f}")

    # Save report
    df = pd.DataFrame(results)
    df.to_csv(f"{OUTPUT_DIR}/performance_report.csv", index=False)
    print("-" * 50)
    print(f"Report saved to {OUTPUT_DIR}/performance_report.csv")

if __name__ == "__main__":
    run_benchmark()
