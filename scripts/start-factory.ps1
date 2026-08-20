[CmdletBinding()]
param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required. Install Docker Desktop and retry."
}
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    throw "Created .env. Add OPENAI_API_KEY, then run this script again."
}

$arguments = @("compose", "up", "-d")
if ($Build) {
    $arguments += "--build"
}
& docker @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE."
}

Write-Host "Factory UI: http://localhost:8000"
Write-Host "Traces:    http://localhost:16686"
Write-Host "Metrics:   http://localhost:3000"
Write-Host "Prometheus:http://localhost:9090"
