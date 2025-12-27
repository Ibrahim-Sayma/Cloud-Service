$body = @{ filename='test.csv'; job_type='ml'; params = @{ algorithm='linear_regression'; target_col='salary'; feature_cols=@('age') } } | ConvertTo-Json -Depth 5
Write-Output "Request body:"
Write-Output $body

try {
    $r = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/jobs/submit' -ContentType 'application/json' -Body $body
} catch {
    Write-Output "Submit failed: $_"
    exit 1
}

Write-Output "Submitted job_id: $($r.job_id)"
$job_id = $r.job_id

for ($i=0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    try {
        $s = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/jobs/$job_id"
        Write-Output "Status: $($s.status)"
        if ($s.status -eq 'COMPLETED' -or $s.status -eq 'FAILED') { break }
    } catch {
        Write-Output "Status request failed: $_"
        break
    }
}

Write-Output "\n--- Log tail ---"
Get-Content -Path ".\storage\$job_id.log" -Tail 200 -ErrorAction SilentlyContinue

Write-Output "\n--- Params file (if any) ---"
Get-Content -Path ".\storage\$job_id`_params.json" -ErrorAction SilentlyContinue

Write-Output "\n--- Results file ---"
Get-Content -Path ".\storage\$job_id`_results.json" -ErrorAction SilentlyContinue
