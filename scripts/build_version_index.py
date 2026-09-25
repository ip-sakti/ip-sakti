"""
Build deployment version index artifacts under indexes/version/.
Uses Gemini Embedding 2 at 768 dimensions and BM25SparseStore.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from ip_sakti.models.document import KnowledgeDocument
from ip_sakti.retrieval.bm25_store import BM25SparseStore
from ip_sakti.retrieval.embeddings import EmbeddingGenerator
from ip_sakti.retrieval.faiss_store import FAISSVectorStore

doc_files = [
    "data/knowledge/doc_ayush_form_24d.json",
    "data/knowledge/doc_ayush_rule_158b.json",
    "data/knowledge/doc_biodiversity_act_2002.json",
    "data/knowledge/doc_ip_india_ayush_guidelines_2025.json",
    "data/knowledge/doc_nba_abs_regulations_2014.json",
    "data/knowledge/doc_patents_act_3p.json",
    "data/knowledge/doc_tkdl_wipo_policy.json",
]

documents = []
for file_path in doc_files:
    try:
        res = subprocess.run(
            ["git", "show", f"johney/antigravity:{file_path}"],
            capture_output=True, text=True, check=True
        )
        doc_data = json.loads(res.stdout)
        documents.append(KnowledgeDocument.model_validate(doc_data))
    except Exception as exc:
        print(f"Error loading {file_path}: {exc}")

print(f"Loaded {len(documents)} KnowledgeDocuments.")

version_dir = Path("indexes/version")
version_dir.mkdir(parents=True, exist_ok=True)

# 1. Build & Save FAISS Index (Gemini Embedding 2 768d)
embed_gen = EmbeddingGenerator()
print(f"Generating embeddings using Gemini Embedding 2 (dimension: {embed_gen.dimension})...")
embeddings = embed_gen.embed_texts([doc.content for doc in documents])

faiss_store = FAISSVectorStore()
faiss_store.build_index(documents, embeddings)
faiss_store.save(version_dir)
print(f"Saved FAISS index to {version_dir / 'faiss.index'}")

# 2. Build & Save BM25 Index
bm25_store = BM25SparseStore()
bm25_store.build_index(documents)
bm25_store.save(version_dir)
print(f"Saved BM25 index to {version_dir / 'bm25.pkl'}")

print("Successfully created indexes/version/ artifacts!")
