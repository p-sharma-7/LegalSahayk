import json
import faiss
import numpy as np
import os
import re
import pickle
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

# ==========================================
# 1. INITIALIZE EMBEDDING MODEL
# ==========================================
print("Loading Dense Embedding Model for Ingestion...")
# We use CPU or GPU here; it frees up after the script finishes.
embedding_model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cuda")
embedding_dimension = embedding_model.get_sentence_embedding_dimension()

# ==========================================
# 2. INGESTION FUNCTIONS
# ==========================================
def ingest_statutes(json_filepath, output_prefix="db_statutes"):
    print(f"\n--- Ingesting Statutes from {json_filepath} ---")
    with open(json_filepath, "r", encoding="utf-8") as f:
        statutes_data = json.load(f)

    metadata = []
    texts_to_embed = []
    tokenized_corpus = []

    for i, item in enumerate(statutes_data):
        enriched_text = f"Act: {item['title']} | Section: {item['section']}\n{item['full_text']}"
        texts_to_embed.append(enriched_text)
        metadata.append({
            "id": i,
            "title": item.get("title", ""),
            "section": item.get("section", ""),
            "text": item.get("full_text", "")
        })
        tokenized_corpus.append(enriched_text.lower().split())

    # Build and Save FAISS
    print("Building and saving Dense Index (FAISS)...")
    embeddings = embedding_model.encode(texts_to_embed, convert_to_numpy=True, normalize_embeddings=True)
    faiss_index = faiss.IndexFlatIP(embedding_dimension)
    faiss_index.add(embeddings)
    faiss.write_index(faiss_index, f"{output_prefix}.faiss")

    # Build and Save BM25
    print("Building and saving Sparse Index (BM25)...")
    bm25_index = BM25Okapi(tokenized_corpus)
    with open(f"{output_prefix}_bm25.pkl", "wb") as f:
        pickle.dump(bm25_index, f)

    # Save Metadata
    with open(f"{output_prefix}_meta.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f)
        
    print(f"Statutes successfully saved to {output_prefix}.*")

def ingest_contract(contract_text, output_prefix="db_contract"):
    print("\n--- Ingesting Dynamic Contract ---")
    raw_chunks = re.split(r'\n(?=\d+\.\s)', contract_text)
    
    metadata = []
    texts_to_embed = []
    tokenized_corpus = []

    for i, chunk in enumerate(raw_chunks):
        chunk = chunk.strip()
        if not chunk: continue
        
        texts_to_embed.append(chunk)
        metadata.append({
            "id": i,
            "title": "Uploaded Contract",
            "section": f"Clause {i+1}",
            "text": chunk
        })
        tokenized_corpus.append(chunk.lower().split())

    # Build and Save FAISS
    print("Building and saving Dense Index (FAISS)...")
    embeddings = embedding_model.encode(texts_to_embed, convert_to_numpy=True, normalize_embeddings=True)
    faiss_index = faiss.IndexFlatIP(embedding_dimension)
    faiss_index.add(embeddings)
    faiss.write_index(faiss_index, f"{output_prefix}.faiss")

    # Build and Save BM25
    print("Building and saving Sparse Index (BM25)...")
    bm25_index = BM25Okapi(tokenized_corpus)
    with open(f"{output_prefix}_bm25.pkl", "wb") as f:
        pickle.dump(bm25_index, f)

    # Save Metadata
    with open(f"{output_prefix}_meta.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f)
        
    print(f"Contract successfully saved to {output_prefix}.*")

# ==========================================
# 3. EXECUTE INGESTION
# ==========================================
if __name__ == "__main__":
    # 1. Ingest Statutes
    json_file = "data_scrapping\sme_statutes_db.json"
    if os.path.exists(json_file):
        ingest_statutes(json_file, output_prefix="db_statutes")
    else:
        print(f"Error: {json_file} not found.")

    # 2. Ingest Sample Contract
    sample_contract = """MASTER SERVICE AGREEMENT
    1. PAYMENT TERMS: The Client agrees to pay the Vendor within 45 days.
    2. TERMINATION: Either party may terminate with 30-day notice.
    3. GOVERNING LAW: Governed by the laws of India."""
    
    ingest_contract(sample_contract, output_prefix="db_contract")
    print("\nAll data ingested. You can now run the agent script.")