# LegalSahyak

LegalSahyak is a local legal question-answering system focused on Indian statutes and contract clauses. It combines hybrid retrieval (FAISS + BM25), cross-encoder reranking, and a local GGUF model for final answer generation.

This repository includes:
- Data scraping and preprocessing for Indian statutes
- Retrieval index generation
- A FastAPI backend for chat inference
- A React + TypeScript frontend UI
- Training and benchmarking utilities

This project is intended for research and internal tooling. It does not provide legal advice.

## How it works

1. **Ingestion** (`ingestion.py`)
   - Builds dense embeddings using `BAAI/bge-small-en-v1.5`
   - Builds sparse BM25 index
   - Saves FAISS index, BM25 index, and metadata JSON
2. **Query**
   - Hybrid retrieval from statutes and contract clauses
   - Reranks with `BAAI/bge-reranker-large`
3. **Generation**
   - Uses a local GGUF model via `llama_cpp` to produce final answers

## Repository layout

```text
.
|-- backend.py                 FastAPI backend (API endpoints)
|-- ingestion.py               Build retrieval databases (FAISS + BM25 + metadata)
|-- run_agent.py               Local CLI agent runner
|-- db_statutes.*              Generated statutes indices (created by ingestion)
|-- db_contract.*              Generated contract indices (created by ingestion)
|-- data_scrapping/            India Code scraping and PDF parsing
|-- models/                    Training scripts and local GGUF model
|-- frontend/                  React + TypeScript UI (Vite)
|-- scripts/smoke_test.py      Environment and artifact checks
|-- test_integration.py        API integration test (requires backend running)
|-- requirements.txt           Core dependencies
|-- requirements-training.txt  Optional training dependencies
|-- setup.ps1                  Windows setup helper
```

## Requirements

- Python 3.10+ (recommended 3.10 or 3.11)
- Node.js 18+ (for frontend)
- CMake and a C++ compiler for `llama_cpp` builds
- Disk space:
  - Model file: ~4.7 GB
  - Indices: ~35 MB for sample data

Optional:
- CUDA GPU for faster embedding and LLM inference

## Installation

### Windows PowerShell (recommended)

```powershell
.\setup.ps1
```

Optional training stack:

```powershell
.\setup.ps1 -WithTraining
```

### Linux/macOS (manual)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Optional training dependencies:

```bash
pip install -r requirements-training.txt
```

## Model setup (GGUF)

The backend will load a local GGUF model if present. If not found, it will attempt to download from Hugging Face.

### Option A: Use a local GGUF file (recommended)

1. Place the model at:

```
models/LegalSahyak_q4_k_m.gguf
```

2. Optionally set the model path in `.env`:

```
MODEL_PATH=models/LegalSahyak_q4_k_m.gguf
```

### Option B: Download from Hugging Face

The backend uses:
- Repo: `pushkarsharma/LegalSahayk_q4_k_m`
- File: `LegalSahyak_q4_k_m.gguf`

If you want to download manually:

```bash
python - <<'PY'
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id="pushkarsharma/LegalSahayk_q4_k_m",
    filename="LegalSahyak_q4_k_m.gguf",
    local_dir="models",
    local_dir_use_symlinks=False
)
PY
```

If the repo is gated or rate-limited, set a token:

```bash
export HUGGINGFACE_HUB_TOKEN=your_token_here
```

Windows (PowerShell):

```powershell
$env:HUGGINGFACE_HUB_TOKEN = "your_token_here"
```

The Hugging Face cache can be redirected:

```bash
export HF_HOME=/path/to/cache
```

## Environment variables

Create a `.env` file at the repo root (do not commit it):

```
DEVICE=cpu
N_GPU_LAYERS=0
MODEL_PATH=models/LegalSahyak_q4_k_m.gguf
DB_DIR=LegalSahyak
```

Details:
- `DEVICE`: `cpu` or `cuda` for embedding and reranking in the backend
- `N_GPU_LAYERS`: number of layers to offload to GPU for `llama_cpp`
- `MODEL_PATH`: local GGUF file path
- `DB_DIR`: directory for index files

Note: `ingestion.py` currently uses `device="cuda"` for embeddings. If you do not have a GPU, change this to `"cpu"` before running ingestion.

## Build retrieval databases

```bash
python ingestion.py
```

This generates:
- `db_statutes.faiss`
- `db_statutes_bm25.pkl`
- `db_statutes_meta.json`
- `db_contract.faiss`
- `db_contract_bm25.pkl`
- `db_contract_meta.json`

Statutes data input:
```
data_scrapping/sme_statutes_db.json
```

Contract data input:
- A sample contract is embedded in `ingestion.py`
- Replace the `sample_contract` variable with your own clauses

## Run the backend (API)

```bash
uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

API endpoints:
- `GET /api/status`
- `POST /api/chat`

Example request:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the penalty for GST evasion?",
    "history": []
  }'
```

Swagger docs:
```
http://localhost:8000/docs
```

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open:
```
http://localhost:5173
```

The frontend uses:
```
VITE_API_URL=http://localhost:8000
```

## Smoke test

```bash
python scripts/smoke_test.py
```

## Integration test (backend must be running)

```bash
python test_integration.py
```

## Data scraping workflow (optional)

Use this only if you want to rebuild `sme_statutes_db.json` from source.

```bash
cd data_scrapping
python act_link_finder.py
python data_download.py
python analyze_statutes.py
cd ..
```

Then rebuild indices:

```bash
python ingestion.py
```

## Training and benchmarking (optional)

- `models/train.py` for fine-tuning and export
- `models/analyze_model.py` for CPU vs GPU benchmark and emissions

Run from the `models/` directory if relative paths are used.

## Troubleshooting

**Missing database files**
- Run `python ingestion.py`

**CUDA or device errors**
- Change `DEVICE=cpu` in `.env`
- For ingestion, change `device="cuda"` to `"cpu"`

**Model not found**
- Ensure `models/LegalSahyak_q4_k_m.gguf` exists
- Or set `MODEL_PATH` in `.env`

**Slow responses**
- CPU inference is slow for GGUF models
- Use GPU and increase `N_GPU_LAYERS` if available

**faiss installation problems on Windows**
- Use `faiss-cpu` first
- GPU builds require additional system setup

## Reproducibility checklist

- Use a fresh virtual environment
- Install from `requirements.txt`
- Keep model path valid
- Rebuild indices after changing statute or contract data
- Do not commit generated `.faiss`, `.pkl`, or `.json` files

## License

Add a license file if you plan to distribute this repository.
