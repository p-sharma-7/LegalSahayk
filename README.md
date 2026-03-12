# LegalSahyak

LegalSahyak is a local legal question-answering pipeline that combines:

- Hybrid retrieval (`FAISS` + `BM25`) over statutes and contract clauses
- Cross-encoder reranking for better relevance
- A local `GGUF` LLM (via `llama-cpp`/LangChain) for final answer generation

The project also includes scripts to scrape and process Indian statute data from India Code, plus model training and benchmarking utilities.

## Repository Layout

```text
.
|-- ingestion.py                  # Build retrieval databases (FAISS + BM25 + metadata)
|-- run_agent.py                  # Run LangChain ReAct agent with local GGUF model
|-- db_statutes.*                 # Built statutes vector/sparse indices + metadata
|-- db_contract.*                 # Built contract vector/sparse indices + metadata
|-- data_scrapping/
|   |-- act_link_finder.py        # Collect act links from India Code search pages
|   |-- data_download.py          # Download + parse PDF content into section chunks
|   |-- analyze_statutes.py       # Dataset analytics
|   |-- sme_statutes_db.json      # Scraped statute dataset (input for ingestion)
|-- models/
|   |-- train.py                  # Fine-tuning/export pipeline
|   |-- analyze_model.py          # CPU vs GPU benchmark + codecarbon metrics
|   |-- LegalSahyak_q4_k_m.gguf   # Local inference model used by run_agent.py
```

## How It Works

1. `ingestion.py` reads statutes JSON and contract text.
2. It creates:
	- Dense index with sentence embeddings (`BAAI/bge-small-en-v1.5`) and `FAISS`
	- Sparse index with `BM25`
	- Metadata JSON files
3. `run_agent.py` loads indices + reranker (`BAAI/bge-reranker-large`).
4. A ReAct agent chooses between:
	- `search_contract`
	- `search_statutes`
5. The final answer is generated using local `LlamaCpp` with the GGUF model.

## Prerequisites

- Python 3.10+ (recommended)
- Optional CUDA GPU (current scripts default to `device="cuda"` for embedding/reranking)
- GGUF model file available at `models/LegalSahyak_q4_k_m.gguf`

## Installation

Use the bootstrap script for the most reproducible setup.

### Recommended (Windows PowerShell)

```powershell
.\setup.ps1
```

Optional training stack:

```powershell
.\setup.ps1 -WithTraining
```

### Manual Setup

Create and activate a virtual environment, then install dependencies.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

Optional training dependencies:

```powershell
pip install -r requirements-training.txt
```

Legacy note: `requirements.text` is retained for compatibility, but `requirements.txt` is the canonical dependency file.

## Quick Start

### 1) Build Retrieval Databases

```powershell
python ingestion.py
```

If you rebuilt statutes from scraping, ensure `data_scrapping/sme_statutes_db.json` exists before ingestion.

Optional environment check before running the agent:

```powershell
python scripts/smoke_test.py
```

This creates or updates:

- `db_statutes.faiss`
- `db_statutes_bm25.pkl`
- `db_statutes_meta.json`
- `db_contract.faiss`
- `db_contract_bm25.pkl`
- `db_contract_meta.json`

### 2) Run the Agent

```powershell
python run_agent.py
```

By default, the script executes a built-in legal query in `run_agent.py` and prints the final output.

## Data Scraping Workflow (Optional)

Use this if you want to rebuild `sme_statutes_db.json` from fresh sources.

1. Collect act links:

```powershell
cd data_scrapping
python act_link_finder.py
```

2. Download/parse PDFs into section-level JSON:

```powershell
python data_download.py
```

3. (Optional) Analyze scraped dataset:

```powershell
python analyze_statutes.py
```

4. Return to repo root and run ingestion:

```powershell
cd ..
python ingestion.py
```

## Training and Benchmarking

- Fine-tuning/export script: `models/train.py`
- Inference benchmark (CPU vs GPU + emissions): `models/analyze_model.py`

Run from `models/` directory if relative model paths are used.

## Troubleshooting

- `FileNotFoundError` for database artifacts: Run `python ingestion.py` first.
- CUDA/device errors on systems without GPU: Update `device="cuda"` to `device="cpu"` in `ingestion.py` and `run_agent.py`.
- GGUF model not found: Ensure `models/LegalSahyak_q4_k_m.gguf` exists or update `model_path` in `run_agent.py`.
- `faiss` install issues on Windows: Start with `faiss-cpu`; GPU builds often need extra system setup.
- PowerShell script execution is blocked: run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and retry `./setup.ps1`.

## Reproducibility Checklist

- Use Python 3.10+ and a fresh `.venv`
- Install from `requirements.txt` (not ad-hoc package lists)
- Keep model path valid: `models/LegalSahyak_q4_k_m.gguf`
- Rebuild indices with `python ingestion.py` after changing statute/contract data
- Commit code and config changes separately from generated `.faiss`/`.pkl` files

## Notes

- `run_agent.py` currently uses a hardcoded example query. You can replace the `query` variable under `if __name__ == "__main__":` for custom questions.
- Keep file paths relative to repository root when running scripts.
