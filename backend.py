import os
import json
import pickle
import time
from typing import List, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

# Load local environment file if it exists
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()


# ── LLM ──────────────────────────────────────────────────────────────────────
from llama_cpp import Llama

# ── Retrieval ─────────────────────────────────────────────────────────────────
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
EMBED_MODEL     = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL  = "BAAI/bge-reranker-large"
N_CTX           = 4096
N_GPU_LAYERS    = int(os.getenv("N_GPU_LAYERS", "0"))
TOP_K_RETRIEVE  = 10
TOP_K_RERANK    = 3
DEVICE          = os.getenv("DEVICE", "cpu")

# Paths — db files live in the LegalSahyak/ subdirectory
DB_DIR           = os.getenv("DB_DIR", "LegalSahyak")
LOCAL_MODEL_PATH = os.getenv("MODEL_PATH", "models/LegalSahyak_q4_k_m.gguf")
HF_MODEL_REPO    = "pushkarsharma/LegalSahayk_q4_k_m"
HF_MODEL_FILE    = "LegalSahyak_q4_k_m.gguf"
MIN_MODEL_SIZE   = 200 * 1024 * 1024  # 200 MB minimum — guards against truncated downloads

app = FastAPI(title="LegalSahyak API", description="AI-powered Indian Legal Assistant Backend")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the Vite host (e.g. http://localhost:5173)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# State Initialisation
# ─────────────────────────────────────────────────────────────────────────────
print("⚙️ Loading models & databases...")

try:
    embedder = SentenceTransformer(EMBED_MODEL, device=DEVICE)
    reranker = CrossEncoder(RERANKER_MODEL, device=DEVICE)
except Exception as e:
    print(f"⚠️ Error loading sentence transformers: {e}")
    embedder = None
    reranker = None

def load_index(prefix: str, base_dir: str = DB_DIR):
    path = os.path.join(base_dir, prefix) if base_dir else prefix
    if not os.path.exists(f"{path}.faiss"):
        raise FileNotFoundError(f"Missing database file: {path}.faiss")
    index = faiss.read_index(f"{path}.faiss")
    with open(f"{path}_bm25.pkl", "rb") as f:
        bm25 = pickle.load(f)
    with open(f"{path}_meta.json", "r") as f:
        meta = json.load(f)
    return index, bm25, meta

try:
    statute_index, statute_bm25, statute_meta = load_index("db_statutes")
    contract_index, contract_bm25, contract_meta = load_index("db_contract")
    print(f"✅ Databases loaded from '{DB_DIR}/' directory.")
    db_loaded = True
    print("✅ Databases loaded successfully.")
except Exception as e:
    print(f"⚠️ Error loading database indices: {e}")
    db_loaded = False
    statute_index, statute_bm25, statute_meta = None, None, None
    contract_index, contract_bm25, contract_meta = None, None, None

# Load LLM
llm = None
try:
    model_size = os.path.getsize(LOCAL_MODEL_PATH) if os.path.exists(LOCAL_MODEL_PATH) else 0
    local_ok = model_size >= MIN_MODEL_SIZE
    if not local_ok and os.path.exists(LOCAL_MODEL_PATH):
        print(f"⚠️  GGUF file is only {model_size // (1024*1024)} MB — likely corrupted. Re-downloading...")
        os.remove(LOCAL_MODEL_PATH)
    if local_ok:
        print(f"⚙️ Loading GGUF model from local path: {LOCAL_MODEL_PATH} ({model_size // (1024*1024)} MB)")
        llm = Llama(
            model_path=LOCAL_MODEL_PATH,
            n_ctx=N_CTX,
            n_gpu_layers=N_GPU_LAYERS,
            verbose=False
        )
    else:
        print(f"⚙️ Downloading and loading GGUF model from HuggingFace ({HF_MODEL_REPO})")
        llm = Llama.from_pretrained(
            repo_id=HF_MODEL_REPO,
            filename=HF_MODEL_FILE,
            n_ctx=N_CTX,
            n_gpu_layers=N_GPU_LAYERS,
            verbose=False
        )
    print("✅ LLM loaded successfully.")
except Exception as e:
    print(f"⚠️ Error loading LLM: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Search & Generation Logic
# ─────────────────────────────────────────────────────────────────────────────
def hybrid_search(query: str, faiss_index, bm25, meta, top_k=TOP_K_RETRIEVE):
    if not embedder or not faiss_index:
        return []
    q_emb = embedder.encode([query], normalize_embeddings=True).astype("float32")

    # Dense Search
    _, dense_ids = faiss_index.search(q_emb, top_k)
    dense_ids = dense_ids[0].tolist()

    # Sparse Search (BM25)
    tokens = query.lower().split()
    bm25_scores = bm25.get_scores(tokens)
    sparse_ids = np.argsort(bm25_scores)[::-1][:top_k].tolist()

    # Merge Unique Results
    seen = set()
    docs = []
    for idx in dense_ids + sparse_ids:
        if idx not in seen and 0 <= idx < len(meta):
            seen.add(idx)
            docs.append(meta[idx])
    return docs[:top_k]

def rerank(query: str, docs: list, top_k=TOP_K_RERANK):
    if not docs or not reranker:
        return docs[:top_k]
    pairs = [(query, d.get("text", "")) for d in docs]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    return [d for _, d in ranked[:top_k]]

SYSTEM_PROMPT = (
    "You are LegalSahyak, an expert AI legal assistant specialising in Indian law. "
    "Answer only based on the retrieved context provided. "
    "If the context does not contain enough information to fully answer, state: 'Insufficient context provided.' "
    "Always cite the statute name and section when available. "
    "Do NOT invent legal provisions or make assumptions outside the context."
)

def build_context(statute_docs, contract_docs):
    parts = []
    if statute_docs:
        parts.append("## Relevant Statutes")
        for i, d in enumerate(statute_docs, 1):
            title = d.get("act_title", d.get("title", "Unknown Act"))
            sec   = d.get("section_title", d.get("section", ""))
            text  = d.get("text", "")
            parts.append(f"[S{i}] {title} — {sec}\n{text}")
    if contract_docs:
        parts.append("## Relevant Contract Clauses")
        for i, d in enumerate(contract_docs, 1):
            title = d.get("title", f"Clause {i}")
            text  = d.get("text", "")
            parts.append(f"[C{i}] {title}\n{text}")
    return "\n\n".join(parts) if parts else "No relevant context found."

# ─────────────────────────────────────────────────────────────────────────────
# API Models & Routes
# ─────────────────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: List[Tuple[str, str]] = []

class SourceInfo(BaseModel):
    type: str
    title: str
    section: str = ""
    snippet: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]

# TODO: Add streaming responses for long generations to improve perceived latency.
@app.get("/api/status")
def get_status():
    return {
        "status": "ready" if (llm is not None and db_loaded) else "initializing",
        "llm_loaded": llm is not None,
        "databases_loaded": db_loaded,
        "device": DEVICE
    }

@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    if not llm:
        raise HTTPException(status_code=503, detail="LLM is not loaded yet.")
    if not db_loaded:
        raise HTTPException(status_code=503, detail="Database indices are not loaded yet.")

    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # Retrieve from both databases
    stat_docs = rerank(query, hybrid_search(query, statute_index, statute_bm25, statute_meta))
    cont_docs = rerank(query, hybrid_search(query, contract_index, contract_bm25, contract_meta))
    context = build_context(stat_docs, cont_docs)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]

    try:
        resp = llm.create_chat_completion(
            messages=messages,
            max_tokens=512,
            temperature=0.1,
        )
        answer = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

    # Format sources
    sources = []
    for d in stat_docs:
        sources.append(SourceInfo(
            type="statute",
            title=d.get("act_title", d.get("title", "Statute")),
            section=d.get("section_title", d.get("section", "")),
            snippet=d.get("text", "")[:300] + "..."
        ))
    for d in cont_docs:
        sources.append(SourceInfo(
            type="contract",
            title=d.get("title", "Contract Clause"),
            section="",
            snippet=d.get("text", "")[:300] + "..."
        ))

    return ChatResponse(answer=answer, sources=sources)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
