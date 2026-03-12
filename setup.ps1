param(
    [switch]$WithTraining
)

$ErrorActionPreference = "Stop"

Write-Host "[1/5] Checking Python..."
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available on PATH. Install Python 3.10+ and retry."
}

if (-not (Test-Path ".venv")) {
    Write-Host "[2/5] Creating virtual environment..."
    python -m venv .venv
} else {
    Write-Host "[2/5] Virtual environment already exists."
}

Write-Host "[3/5] Activating virtual environment..."
.\.venv\Scripts\Activate.ps1

Write-Host "[4/5] Installing base dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if ($WithTraining) {
    Write-Host "[5/5] Installing optional training dependencies..."
    python -m pip install -r requirements-training.txt
} else {
    Write-Host "[5/5] Skipping optional training dependencies."
}

Write-Host "Setup complete."
Write-Host "Next steps:"
Write-Host "  python ingestion.py"
Write-Host "  python run_agent.py"
