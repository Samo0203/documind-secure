import json
import logging
import os
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Per-user FAISS vector store that persists index and metadata to disk.
    Each chunk is stored with its metadata (doc_id, filename, page, text).
    """

    def __init__(self, user_id: str, index_dir: str = "./faiss_indexes"):
        self.user_id = user_id
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.index_dir / f"{user_id}.index"
        self.meta_path = self.index_dir / f"{user_id}.meta"

        self._index = None
        self._metadata: List[dict] = []  # parallel list to FAISS vectors
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────

    def _load(self):
        """Load existing FAISS index and metadata from disk if they exist."""
        if self.index_path.exists() and self.meta_path.exists():
            try:
                import faiss
                self._index = faiss.read_index(str(self.index_path))
                with open(self.meta_path, "rb") as f:
                    self._metadata = pickle.load(f)
                logger.info("Loaded FAISS index for user %s (%d vectors)", self.user_id, len(self._metadata))
            except Exception as e:
                logger.warning("Could not load FAISS index for user %s: %s", self.user_id, e)
                self._index = None
                self._metadata = []

    def _save(self):
        """Persist the FAISS index and metadata to disk."""
        try:
            import faiss
            if self._index is not None:
                faiss.write_index(self._index, str(self.index_path))
            with open(self.meta_path, "wb") as f:
                pickle.dump(self._metadata, f)
        except Exception as e:
            logger.error("Failed to save FAISS index for user %s: %s", self.user_id, e)

    # ── Operations ───────────────────────────────────────────────────────

    def add_chunks(
        self,
        embeddings: List[List[float]],
        chunks: List[str],
        document_id: str,
        filename: str,
    ):
        """Add embedded chunks to the user's FAISS index."""
        import faiss

        if not embeddings:
            return

        vectors = np.array(embeddings, dtype=np.float32)
        dim = vectors.shape[1]

        if self._index is None:
            self._index = faiss.IndexFlatL2(dim)

        self._index.add(vectors)

        for i, chunk_text in enumerate(chunks):
            self._metadata.append({
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,
                "text": chunk_text,
                "page": None,  # page-level tagging future improvement
            })

        self._save()
        logger.info("Added %d chunks for doc %s to FAISS (user %s)", len(chunks), document_id, self.user_id)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """
        Search for the top-k most similar chunks.
        Optionally filter by document_ids.
        Returns list of metadata dicts with 'score' added.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        query_vec = np.array([query_embedding], dtype=np.float32)
        k = min(top_k * 3, self._index.ntotal)  # fetch extra for filtering
        distances, indices = self._index.search(query_vec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self._metadata):
                continue
            meta = self._metadata[idx].copy()
            meta["score"] = float(dist)
            if document_ids and meta["document_id"] not in document_ids:
                continue
            results.append(meta)
            if len(results) >= top_k:
                break

        return results

    def delete_document(self, document_id: str):
        """
        Remove all chunks for a document.
        FAISS doesn't support deletion natively, so we rebuild the index.
        """
        import faiss

        keep_indices = [
            i for i, m in enumerate(self._metadata) if m["document_id"] != document_id
        ]

        if len(keep_indices) == len(self._metadata):
            return  # nothing to remove

        if not keep_indices:
            self._index = None
            self._metadata = []
            self._save()
            return

        # Reconstruct: fetch all vectors, filter, rebuild
        old_index = self._index
        dim = old_index.d
        all_vectors = np.zeros((old_index.ntotal, dim), dtype=np.float32)
        old_index.reconstruct_n(0, old_index.ntotal, all_vectors)

        kept_vectors = all_vectors[keep_indices]
        self._metadata = [self._metadata[i] for i in keep_indices]
        self._index = faiss.IndexFlatL2(dim)
        self._index.add(kept_vectors)
        self._save()
        logger.info("Rebuilt FAISS index for user %s after deleting doc %s", self.user_id, document_id)
