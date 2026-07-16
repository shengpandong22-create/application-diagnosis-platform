param([string]$BaseUrl = 'http://127.0.0.1:8000')

$ErrorActionPreference = 'Stop'
$requestId = "real-model-$([guid]::NewGuid().ToString('N'))"
$headers = @{ 'X-Request-ID' = $requestId }
$health = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -Headers $headers
if ($health.status -ne 'ready') { throw 'API readiness check failed' }
$body = @{
    title = 'Phase 0A real model smoke test'
    symptom = 'Java order API returns HTTP 500 during checkout'
    submitted_log = 'java.lang.NullPointerException: order.customer is null at com.example.OrderService.checkout(OrderService.java:42)'
} | ConvertTo-Json
$diagnosis = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/diagnoses" -Headers $headers -ContentType 'application/json' -Body $body
$result = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/diagnoses/$($diagnosis.id)/runs" -Headers $headers
$runs = Invoke-RestMethod -Uri "$BaseUrl/api/v1/diagnoses/$($diagnosis.id)/runs" -Headers $headers
$stored = Invoke-RestMethod -Uri "$BaseUrl/api/v1/diagnoses/$($diagnosis.id)" -Headers $headers
if ($result.termination_reason -ne 'completed') {
    $errorCode = if ($runs.Count -gt 0) { $runs[0].error_code } else { 'run_not_recorded' }
    throw "Real model run did not complete: reason=$($result.termination_reason), error_code=$errorCode. Check APP_LLM_* configuration and provider compatibility."
}
if ($null -eq $stored.conclusion) { throw 'Real model run completed without a stored conclusion' }
if ($runs.Count -eq 0 -or $runs[0].tool_call_count -lt 1) { throw 'Real model did not call knowledge__search; inspect provider tool-calling behavior' }
Write-Host "Real model smoke test: PASSED (diagnosis_id=$($diagnosis.id), request_id=$requestId)" -ForegroundColor Green
