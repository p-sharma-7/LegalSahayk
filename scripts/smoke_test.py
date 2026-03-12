"""Quick environment and artifact checks for LegalSahyak."""

from pathlib import Path
import importlib
import sys

REQUIRED_IMPORTS = [
    "numpy",
    "pandas",
    "faiss",
    "sentence_transformers",
    "rank_bm25",
    "langchain",
    "langchain_community",
    "langchain_core",
    "llama_cpp",
    "requests",
    "bs4",
    "fitz",
]

REQUIRED_FILES = [
    "ingestion.py",
    "run_agent.py",
    "data_scrapping/sme_statutes_db.json",
    "models/LegalSahyak_q4_k_m.gguf",
]

OPTIONAL_RUNTIME_FILES = [
    "db_statutes.faiss",
    "db_statutes_bm25.pkl",
    "db_statutes_meta.json",
    "db_contract.faiss",
    "db_contract_bm25.pkl",
    "db_contract_meta.json",
]


def check_imports() -> list[str]:
    failures = []
    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            failures.append(f"import {module_name}: {exc}")
    return failures


def check_files(root: Path, files: list[str]) -> list[str]:
    missing = []
    for rel_path in files:
        if not (root / rel_path).exists():
            missing.append(rel_path)
    return missing


def main() -> int:
    root = Path(__file__).resolve().parent.parent

    print("LegalSahyak smoke test")
    print(f"Repo root: {root}")

    import_failures = check_imports()
    required_missing = check_files(root, REQUIRED_FILES)
    optional_missing = check_files(root, OPTIONAL_RUNTIME_FILES)

    if import_failures:
        print("\nImport failures:")
        for item in import_failures:
            print(f"- {item}")

    if required_missing:
        print("\nMissing required files:")
        for item in required_missing:
            print(f"- {item}")

    if optional_missing:
        print("\nMissing runtime index files (run ingestion.py to generate):")
        for item in optional_missing:
            print(f"- {item}")

    if not import_failures and not required_missing:
        print("\nSmoke test passed.")
        if optional_missing:
            print("Indexes are missing, but this is expected on a fresh clone.")
        return 0

    print("\nSmoke test failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
