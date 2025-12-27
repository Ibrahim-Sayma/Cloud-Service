$jobs = @(
    @{ name = 'Linear Regression'; body = @{ filename='test.csv'; job_type='ml'; params = @{ algorithm='linear_regression'; target_col='salary'; feature_cols=@('age') } } },
    @{ name = 'Logistic Regression'; body = @{ filename='test_classification.csv'; job_type='ml'; params = @{ algorithm='logistic_regression'; target_col='is_high_salary'; feature_cols=@('age') } } },
    @{ name = 'KMeans (k=2)'; body = @{ filename='test.csv'; job_type='ml'; params = @{ algorithm='kmeans'; feature_cols=@('age'); k=2 } } },
    @{ name = 'FPGrowth'; body = @{ filename='test_classification.csv'; job_type='ml'; params = @{ algorithm='fpgrowth'; items_col='name'; minSupport=0.1; minConfidence=0.1 } } }
)

foreach ($job in $jobs) {
    Write-Output "\n=== Submitting: $($job.name) ==="
    $body = $job.body | ConvertTo-Json -Depth 5
    Write-Output $body
    try {
        $r = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/jobs/submit' -ContentType 'application/json' -Body $body
    } catch {
        Write-Output "Submit failed for $($job.name): $_"
        continue
    }
    $job_id = $r.job_id
    Write-Output "Submitted job_id: $job_id"

    for ($i=0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        try {
            $s = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/jobs/$job_id"
            Write-Output "Status: $($s.status)"
            if ($s.status -eq 'COMPLETED' -or $s.status -eq 'FAILED') { break }
        } catch {
            Write-Output "Status request failed: $_"
            # Don't bail the whole job on a transient status error; keep polling
            continue
        }
    }

    Write-Output "\n--- Log tail for $job_id ---"
    Get-Content -Path ".\storage\$job_id.log" -Tail 200 -ErrorAction SilentlyContinue

    Write-Output "\n--- Params file for $job_id ---"
    Get-Content -Path ".\storage\$job_id`_params.json" -ErrorAction SilentlyContinue

    Write-Output "\n--- Results file for $job_id ---"
    Get-Content -Path ".\storage\$job_id`_results.json" -ErrorAction SilentlyContinue
}
