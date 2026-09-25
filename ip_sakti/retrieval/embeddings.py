"""
ip_sakti.retrieval.embeddings — Multilingual embedding generator component.

Wraps sentence-transformers to generate dense vector embeddings for documents
and user queries.  Vectors are normalized to unit L2 norm so that FAISS inner
product search directly computes cosine similarity.

Approved per AGENTS.md §5: Preferred pretrained embedding model is sentence-transformers.
Model name is read from config/settings.yaml models.embedding_model.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import os
from pathlib import Path

# Ensure valid HuggingFace / SentenceTransformers cache path on Windows
if "HF_HOME" in os.environ and not Path(os.environ["HF_HOME"].split(":")[0] + ":\\").exists():
    os.environ["HF_HOME"] = str(Path.home() / ".cache" / "huggingface")
if "SENTENCE_TRANSFORMERS_HOME" in os.environ and not Path(os.environ["SENTENCE_TRANSFORMERS_HOME"].split(":")[0] + ":\\").exists():
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(Path.home() / ".cache" / "torch" / "sentence_transformers")

from ip_sakti.retrieval.exceptions import RetrievalError
from ip_sakti.utils.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates normalized dense embeddings using Google Gemini Embedding API
    (models/gemini-embedding-2 with 768 dimensions) or lazy-loaded SentenceTransformer.

    Parameters
    ----------
    model_name :
        HuggingFace model identifier or Gemini model string.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Initialise embedding model using config or explicit parameter."""
        cfg = get_settings()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = (
            model_name
            or cfg.get("models", {}).get("embedding_model", "models/gemini-embedding-2")
        )
        self.use_gemini = bool(self.gemini_api_key)
        self._model: Any | None = None
        logger.debug(
            "EmbeddingGenerator initialised",
            extra={"model_name": self.model_name, "use_gemini": self.use_gemini},
        )

    def _get_model(self) -> Any:
        """Lazy load the SentenceTransformer model on first use if local fallback required."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(
                    "Loading SentenceTransformer model",
                    extra={"model_name": self.model_name},
                )
                self._model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as exc:
                raise RetrievalError(
                    f"Failed to load embedding model {self.model_name!r}: {exc}."
                ) from exc
        return self._model

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        """
        Generate L2-normalized float32 embeddings for a sequence of document strings.

        Parameters
        ----------
        texts :
            List or sequence of strings to embed.

        Returns
        -------
        np.ndarray
            2D float32 numpy array of shape (len(texts), dimension).
        """
        if not texts:
            dim = self.dimension
            return np.empty((0, dim), dtype=np.float32)

        clean_texts = [t.strip() for t in texts]

        if self.use_gemini:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.gemini_api_key)
                vectors = []
                for text in clean_texts:
                    res = genai.embed_content(
                        model="models/gemini-embedding-2",
                        content=text,
                        task_type="retrieval_document",
                        output_dimensionality=768,
                    )
                    v = np.array(res["embedding"], dtype=np.float32)
                    norm = np.linalg.norm(v)
                    if norm > 0:
                        v = v / norm
                    vectors.append(v)
                return np.array(vectors, dtype=np.float32)
            except Exception as exc:
                logger.warning(f"Gemini document embedding failed: {exc}. Falling back to SentenceTransformer.")
                self.use_gemini = False

        model = self._get_model()
        try:
            embeddings = model.encode(
                clean_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embeddings.astype(np.float32)
        except Exception as exc:
            raise RetrievalError(
                f"Embedding generation failed for {len(texts)} texts: {exc}"
            ) from exc

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate L2-normalized float32 embedding for a single query string.

        Parameters
        ----------
        query :
            Query text string.

        Returns
        -------
        np.ndarray
            1D float32 array of shape (dimension,).
        """
        stripped = query.strip()
        if not stripped:
            raise RetrievalError("Cannot generate embedding for empty query.")

        if self.use_gemini:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.gemini_api_key)
                res = genai.embed_content(
                    model="models/gemini-embedding-2",
                    content=stripped,
                    task_type="retrieval_query",
                    output_dimensionality=768,
                )
                v = np.array(res["embedding"], dtype=np.float32)
                norm = np.linalg.norm(v)
                if norm > 0:
                    v = v / norm
                return v
            except Exception as exc:
                logger.warning(f"Gemini query embedding failed: {exc}. Falling back to SentenceTransformer.")
                self.use_gemini = False

        arr = self.embed_texts([stripped])
        return arr[0]

    @property
    def dimension(self) -> int:
        """Return the vector embedding dimension of the loaded model."""
        if self.use_gemini:
            return 768
        model = self._get_model()
        dim = model.get_sentence_embedding_dimension()
        if dim is None:
            raise RetrievalError(
                f"Embedding model {self.model_name!r} did not return a valid dimension."
            )
        return int(dim)

