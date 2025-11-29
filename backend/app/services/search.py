import ast
from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from ..config import Config
from ..repository.rag_repository import (
    fetch_documents_by_ids,
    fetch_images_for_text_chunks,
    fetch_text_chunks,
    fetch_text_chunks_with_vector_search,
)
from .gemini import gemini_client

text_model = SentenceTransformer(Config.TEXT_EMBEDDING_MODEL)


def parse_embedding(emb: Any) -> Optional[List[float]]:
    if emb is None:
        return None
    if isinstance(emb, list):
        return emb
    if isinstance(emb, str):
        try:
            return [float(x) for x in ast.literal_eval(emb)]
        except Exception:
            return None
    return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _rank_chunks(query_embedding: List[float], top_k: int, owner_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Rank chunks by similarity, using pgvector if available, otherwise JSONB fallback."""
    if Config.USE_PGVECTOR:
        try:
            # Use pgvector for efficient vector search
            return fetch_text_chunks_with_vector_search(query_embedding, top_k, owner_user_id=owner_user_id)
        except Exception as e:
            # Fallback to JSONB if pgvector fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"pgvector search failed, falling back to JSONB: {e}")
    
    # Fallback: JSONB-based similarity search
    candidate_pool_size = max(top_k * 20, Config.MAX_CONTEXT_CHUNKS * 5)
    text_chunks = fetch_text_chunks(limit=candidate_pool_size, owner_user_id=owner_user_id)
    scored: List[Dict[str, Any]] = []

    for chunk in text_chunks:
        text_emb = parse_embedding(chunk.get("paired_text_embedding"))
        if text_emb is None:
            continue
        if len(text_emb) != len(query_embedding):
            continue  # Skip dimension mismatches
        sim = cosine_similarity(query_embedding, text_emb)
        scored.append({**chunk, "similarity": sim})

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:top_k]


def search_rag_with_images(query: str, top_k: int = 5, owner_user_id: Optional[int] = None) -> Dict[str, Any]:
    top_k = min(max(top_k, 1), Config.MAX_CONTEXT_CHUNKS)
    _qe = text_model.encode(query)
    query_embedding = _qe.tolist() if hasattr(_qe, "tolist") else (list(_qe) if not isinstance(_qe, list) else _qe)

    ranked_chunks = _rank_chunks(query_embedding, top_k, owner_user_id=owner_user_id)
    chunk_ids = [chunk["id"] for chunk in ranked_chunks]
    images_by_chunk = fetch_images_for_text_chunks(chunk_ids)
    doc_map = fetch_documents_by_ids((ch["document_id"] for ch in ranked_chunks), owner_user_id=owner_user_id)

    context_segments: List[Dict[str, Any]] = []
    for order, chunk in enumerate(ranked_chunks, start=1):
        document = doc_map.get(chunk["document_id"], {})
        document_payload = {
            "id": document.get("id"),
            "filename": document.get("filename"),
            "url": f"/api/documents/{document.get('id')}/file" if document.get("id") else None,
        }
        context_segments.append(
            {
                "order": order,
                "chunk_id": chunk["id"],
                "document_id": chunk["document_id"],
                "page_number": chunk.get("page_number"),
                "chunk_index": chunk.get("chunk_index"),
                "content": chunk.get("content", ""),
                "metadata": {
                    **(chunk.get("metadata") or {}),
                    "similarity": chunk["similarity"],
                },
                "images": images_by_chunk.get(chunk["id"], []),
                "similarity": chunk["similarity"],
                "document": document_payload,
            }
        )

    llm_response = gemini_client.generate(query, context_segments)

    sections_with_images: List[Dict[str, Any]] = []
    for section in llm_response.get("sections", []):
        chunk_ids_in_section = []
        for chunk_id in section.get("chunk_ids", []):
            try:
                chunk_ids_in_section.append(int(chunk_id))
            except (ValueError, TypeError):
                continue

        section_images: List[Dict[str, Any]] = []
        for cid in chunk_ids_in_section:
            section_images.extend(images_by_chunk.get(cid, []))

        sections_with_images.append(
            {
                "title": section.get("title"),
                "text": section.get("text"),
                "chunk_ids": chunk_ids_in_section,
                "images": section_images,
                "documents": [
                    {
                        "id": ctx["document"].get("id"),
                        "filename": ctx["document"].get("filename"),
                        "url": ctx["document"].get("url"),
                        "page_number": ctx.get("page_number"),
                    }
                    for ctx in context_segments
                    if ctx["chunk_id"] in chunk_ids_in_section and ctx.get("document")
                ],
            }
        )

    return {
        "answer": llm_response.get("answer", ""),
        "sections": sections_with_images,
        "context": context_segments,
        "chunks_used": chunk_ids,
        "model": Config.GEMINI_MODEL if gemini_client.enabled else "retriever_only",
        "embedding_model": Config.TEXT_EMBEDDING_MODEL,
        "embedding_dim": Config.TEXT_EMBEDDING_DIM,
        "vector_search": "pgvector" if Config.USE_PGVECTOR else "jsonb",
        "query": query,
        "top_k": top_k,
    }

