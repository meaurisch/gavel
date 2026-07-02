param(
    [Parameter(Position=0)]
    [string]$Task = "Run"
)

# Activate the venv if it exists (studio convention: python -m venv .venv)
$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"

function Invoke-Venv {
    if (Test-Path $venvActivate) { & $venvActivate }
}

function Setup {
    Write-Host "Creating venv, installing deps, bootstrapping task repos..." -ForegroundColor Cyan
    if (-not (Test-Path (Join-Path $PSScriptRoot ".venv"))) {
        python -m venv .venv
    }
    & $venvActivate
    pip install -r requirements.txt
    python cli.py setup
    python cli.py doctor
}

function Run {
    Invoke-Venv
    python cli.py @args
}

function Test {
    Invoke-Venv
    pytest
}

function Watch {
    Invoke-Venv
    ptw . @args
}

function Grade {
    Invoke-Venv
    python cli.py grade @args
}

function Report {
    Invoke-Venv
    python cli.py report @args
}

function Demo {
    Invoke-Venv
    python cli.py demo @args
}

function Doctor {
    Invoke-Venv
    python cli.py doctor
}

# Dispatch
& $Task
