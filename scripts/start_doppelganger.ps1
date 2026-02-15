$ErrorActionPreference = "Stop"

Write-Host "[1/4] Installing dependencies..."
pip install -r requirements.txt

if (!(Test-Path ".env")) {
  Write-Host "[2/4] Creating .env from .env.example"
  Copy-Item ".env.example" ".env"
  Write-Host "Please edit .env and set GEMINI_API_KEY before running."
} else {
  Write-Host "[2/4] .env exists"
}

Write-Host "[3/4] RAG index status"
python scripts/build_semantic_index.py --status

Write-Host "[4/4] Starting server..."
python run.py
