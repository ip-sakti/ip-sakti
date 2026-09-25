"""
ip_sakti.retrieval — Hybrid RAG retrieval layer.

Public API
----------
    from ip_sakti.retrieval import (
        HybridRAGPipeline,
        DocumentChunker,
        EmbeddingGenerator,
        FAISSVectorStore,
        BM25SparseStore,
        ReciprocalRankFusion,
        FusedCandidate,
        CrossEncoderReranker,
        RetrievalError,
        IndexNotFoundError,
        CorruptIndexError,
        EmptyKnowledgeBaseError,
    )
"""

from ip_sakti.retrieval.bm25_store import BM25SparseStore
from ip_sakti.retrieval.chunker import DocumentChunker
from ip_sakti.retrieval.exceptions import (
    CorruptIndexError,
    EmptyKnowledgeBaseError,
    IndexNotFoundError,
    RetrievalError,
)
from ip_sakti.retrieval.faiss_store import FAISSVectorStore
from ip_sakti.retrieval.fusion import FusedCandidate, ReciprocalRankFusion
from ip_sakti.retrieval.pipeline import HybridRAGPipeline

from ip_sakti.retrieval.sources import AuthorisedSource, SourceRegistry


def __getattr__(name: str):
    if name == "EmbeddingGenerator":
        from ip_sakti.retrieval.embeddings import EmbeddingGenerator
        return EmbeddingGenerator
    if name == "CrossEncoderReranker":
        from ip_sakti.retrieval.reranker import CrossEncoderReranker
        return CrossEncoderReranker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AuthorisedSource",
    "BM25SparseStore",
    "CorruptIndexError",
    "CrossEncoderReranker",
    "DocumentChunker",
    "EmbeddingGenerator",
    "EmptyKnowledgeBaseError",
    "FAISSVectorStore",
    "FusedCandidate",
    "HybridRAGPipeline",
    "IndexNotFoundError",
    "ReciprocalRankFusion",
    "RetrievalError",
    "SourceRegistry",
]

