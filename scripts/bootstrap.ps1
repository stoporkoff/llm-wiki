[CmdletBinding()]
param(
    [switch]$InstallPrerequisites,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

function Test-Command {
    param([Parameter(Mandatory)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Resolve-DockerCommand {
    $Command = Get-Command "docker" -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$MachinePath;$UserPath"
    $Command = Get-Command "docker" -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $KnownPath = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $KnownPath) {
        return $KnownPath
    }

    return $null
}

$DockerCommand = Resolve-DockerCommand
if (-not $DockerCommand) {
    if (-not $InstallPrerequisites) {
        throw "Docker is not installed. Re-run with -InstallPrerequisites or install Docker Desktop."
    }
    if (-not (Test-Command "winget")) {
        throw "winget is required for automatic prerequisite installation."
    }
    Write-Host "Installing Docker Desktop..."
    winget install --exact --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    Write-Host "Docker Desktop was installed. Start it, finish first-run setup, then run this script again."
    exit 0
}

$DockerReady = $true
try {
    & $DockerCommand info | Out-Null
    $DockerReady = $LASTEXITCODE -eq 0
} catch {
    $DockerReady = $false
}
if (-not $DockerReady) {
    throw "Docker Desktop is installed but its engine is not running. Start Docker Desktop and retry."
}

if (-not $SkipBuild) {
    & $DockerCommand build --tag llm-wiki:local .
    if ($LASTEXITCODE -ne 0) {
        throw "Docker failed to build the LLM Wiki toolkit image."
    }
}

& $DockerCommand run --rm --volume "${ProjectRoot}:/workspace" llm-wiki:local --root /workspace init
if ($LASTEXITCODE -ne 0) {
    throw "The toolkit could not initialize the file workspace."
}

Write-Host "LLM Wiki workspace initialized."
Write-Host "Open Codex here and invoke `$llm-wiki, or ask it to ingest a file."
