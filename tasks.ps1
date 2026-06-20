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
    # No long-running dev server for a benchmarking CLI; Watch re-runs the test
    # suite on change once pytest exists. Placeholder until P0.1 lands.
    Write-Host "Nothing to watch yet. After P0.1: ptw  (pytest-watch) or re-run Test." -ForegroundColor Yellow
}

function Test {
    if (Test-Path $venvActivate) { & $venvActivate }
    pytest
}

# Dispatch
& $Task
