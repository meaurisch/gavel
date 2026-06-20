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
    # Intended CLI entry point (built by prompts/P0.1 + P1.6 + P3):
    #   setup-bench run|grade|report
    Write-Host "setup-bench CLI not built yet. Work through prompts/ starting at P0.1." -ForegroundColor Yellow
    Write-Host "Once built:  python cli.py --help   (or: setup-bench --help)" -ForegroundColor Gray
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
