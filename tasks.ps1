param(
    [Parameter(Position=0)]
    [string]$Task = "Run"
)

# Activate the venv if it exists (studio convention: python -m venv .venv)
$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"

function Setup {
    Write-Host "Creating venv and installing deps..." -ForegroundColor Cyan
    python -m venv .venv
    & $venvActivate
    if (Test-Path "requirements.txt") {
        pip install -r requirements.txt
    } else {
        Write-Host "No requirements.txt yet — created by prompts/P0.1." -ForegroundColor Yellow
    }
}

function Run {
    if (Test-Path $venvActivate) { & $venvActivate }
    python cli.py @args
}

function Watch {
    if (Test-Path $venvActivate) { & $venvActivate }
    pytest
}

function Test {
    if (Test-Path $venvActivate) { & $venvActivate }
    pytest
}

function Grade {
    if (Test-Path $venvActivate) { & $venvActivate }
    python cli.py grade @args
}

# Dispatch
& $Task
