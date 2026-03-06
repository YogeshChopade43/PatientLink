param(
  [string]$AuthBase = "http://localhost:8000/api",
  [string]$ApiBase = "http://localhost:8001"
)

$ErrorActionPreference = "Stop"

function Invoke-Readiness($name, $url) {
  try {
    $resp = Invoke-WebRequest -Uri $url -Method GET -UseBasicParsing
    $body = $resp.Content | ConvertFrom-Json
    return [PSCustomObject]@{
      service = $name
      status_code = $resp.StatusCode
      ready = $body.ready
      checks = $body.checks
    }
  } catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $statusCode = [int]$_.Exception.Response.StatusCode
    } else {
      $statusCode = 0
    }
    return [PSCustomObject]@{
      service = $name
      status_code = $statusCode
      ready = $false
      checks = @{}
    }
  }
}

$auth = Invoke-Readiness "auth" "$AuthBase/system/readiness/"
$api = Invoke-Readiness "api" "$ApiBase/ops/readiness"

Write-Host "Auth readiness: status=$($auth.status_code) ready=$($auth.ready)"
if ($auth.checks) { $auth.checks | ConvertTo-Json -Depth 5 | Write-Host }
Write-Host "API readiness: status=$($api.status_code) ready=$($api.ready)"
if ($api.checks) { $api.checks | ConvertTo-Json -Depth 5 | Write-Host }

if (-not $auth.ready -or -not $api.ready) {
  Write-Error "Readiness failed. Fix failing checks before production deploy."
  exit 1
}

Write-Host "All readiness checks passed."
