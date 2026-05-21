import json
import faiss
import numpy as np
import pickle
import os
from sentence_transformers import SentenceTransformer, CrossEncoder

# --- LANGCHAIN IMPORTS ---
from langchain_community.llms import LlamaCpp
from langchain_core.tools import tool
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate

# ==========================================
# 1. LOAD MODELS
# ==========================================
print("Loading Embedding & Reranking Models...")
embedding_model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cuda")
reranker_model = CrossEncoder("BAAI/bge-reranker-large", device="cuda")

# ==========================================
# 2. DATABASE LOADER CLASS
# ==========================================
class LoadedDatabase:
    def __init__(self, prefix):
        print(f"Loading {prefix} database from disk...")
        self.faiss_index = faiss.read_index(f"{prefix}.faiss")
        
        with open(f"{prefix}_bm25.pkl", "rb") as f:
            self.bm25_index = pickle.load(f)
            
        with open(f"{prefix}_meta.json", "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

    def retrieve(self, query, top_k=5):
        # Dense
        query_vector = embedding_model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        distances, indices = self.faiss_index.search(query_vector, top_k)
        dense_results = [(idx, distances[0][rank]) for rank, idx in enumerate(indices[0]) if idx != -1]

        # Sparse
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25_index.get_scores(tokenized_query)
        top_bm25_indices = np.argsort(bm25_scores)[::-1][:top_k]
        sparse_results = [(idx, bm25_scores[idx]) for idx in top_bm25_indices if bm25_scores[idx] > 0]

        # RRF Fusion
        rrf_scores = {}
        for rank, (doc_id, _) in enumerate(dense_results):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (60 + rank + 1)
        for rank, (doc_id, _) in enumerate(sparse_results):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (60 + rank + 1)
            
        fused_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [self.metadata[doc_id] for doc_id, _ in fused_results[:top_k]]

# Load Databases
try:
    statute_db = LoadedDatabase("db_statutes")
    contract_db = LoadedDatabase("db_contract")
except FileNotFoundError:
    print("Error: Database files not found. Please run ingest_data.py first.")
    exit()

def rerank_results(query, retrieved_docs, final_top_k=3):
    if not retrieved_docs: return []
    pairs = [[query, doc["text"]] for doc in retrieved_docs]
    scores = reranker_model.predict(pairs)
    for i, doc in enumerate(retrieved_docs):
        doc["rerank_score"] = scores[i]
    ranked_docs = sorted(retrieved_docs, key=lambda x: x["rerank_score"], reverse=True)
    return ranked_docs[:final_top_k]

# ==========================================
# 3. LANGCHAIN TOOLS
# ==========================================
@tool
def search_contract(query: str) -> str:
    """Use this tool to search the uploaded contract for clauses, payment terms, and obligations."""
    results = contract_db.retrieve(query, top_k=5)
    final = rerank_results(query, results, final_top_k=2)
    if not final: return "No relevant clauses found."
    return "\n\n".join([f"Clause: {r['section']}\nText: {r['text']}" for r in final])

@tool
def search_statutes(query: str) -> str:
    """Use this tool to search actual statutory laws, acts, and regulations."""
    results = statute_db.retrieve(query, top_k=10)
    final = rerank_results(query, results, final_top_k=2)
    if not final: return "No relevant statutes found."
    return "\n\n".join([f"Act: {r['title']} - {r['section']}\nText: {r['text']}" for r in final])

tools = [search_contract, search_statutes]

# ==========================================
# 4. LANGCHAIN AGENT SETUP
# ==========================================
print("\nLoading Local GGUF Model via LlamaCpp...")
llm = LlamaCpp(
    model_path="models/LegalSahyak_q4_k_m.gguf", 
    n_gpu_layers=20,  
    n_ctx=4096,       
    temperature=0.0,  
    max_tokens=512,
    verbose=False 
)

template = '''You are a strict legal extraction system. You must answer questions based ONLY on the provided context. 
If the answer is not explicitly in the context, output: 'Insufficient context provided.' Do not infer or provide external legal advice.

You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer based on the observations.
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}'''

prompt = PromptTemplate.from_template(template)
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# ==========================================
# 5. EXECUTION
# ==========================================
if __name__ == "__main__":
    print("\n" + "="*50)
    query = "What is the notice period for terminating the agreement, and does the Integrated Goods and Services Tax Act apply to Jammu and Kashmir?"
    
    try:
        response = agent_executor.invoke({"input": query})
        print(f"\nFinal Verified Output:\n{response['output']}")
    except Exception as e:
        print(f"Agent execution failed: {e}")