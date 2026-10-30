import logging
from typing import List, Optional

from app.core.config import get_settings
from app.services import bedrock as bedrock_service
from app.services.vector_store import VectorStore
from app.models.schemas import Source

logger = logging.getLogger(__name__)
settings = get_settings()

RAG_PROMPT_TEMPLATE = """You are DocuMind, an expert document assistant. Answer the user's question strictly using the provided document context below.

If the answer cannot be found in the context, say: "I could not find an answer to your question in the provided documents."

Do not use your own prior knowledge to answer. Always cite the document source.

---
DOCUMENT CONTEXT:
{context}

---
QUESTION:
{question}

---
ANSWER (be clear, concise, and cite which document sections support your answer):"""


def answer_question(
    user_id: str,
    question: str,
    document_ids: Optional[List[str]] = None,
) -> dict:
    """
    Full RAG pipeline:
    1. Embed the question
    2. Search user's FAISS index (optionally filtered by document_ids)
    3. Build context from top-k chunks
    4. Call Bedrock to generate an answer
    5. Return answer + source citations
    """
    # Step 1: Generate question embedding
    question_embedding = bedrock_service.generate_embeddings(question)
    if question_embedding is None:
        return {
            "answer": "Could not generate question embedding. Please check your AWS configuration.",
            "sources": [],
        }

    # Step 2: Search vector store
    store = VectorStore(user_id=user_id, index_dir=settings.FAISS_INDEX_DIR)
    results = store.search(
        query_embedding=question_embedding,
        top_k=settings.TOP_K_CHUNKS,
        document_ids=document_ids,
    )

    if not results:
        return {
            "answer": (
                "No relevant document content found. "
                "Please upload documents and ensure they have finished processing before asking questions."
            ),
            "sources": [],
        }

    # Step 3: Build context and sources
    context_parts = []
    sources = []
    seen_texts = set()

    for i, result in enumerate(results):
        text = result["text"]
        if text in seen_texts:
            continue
        seen_texts.add(text)

        doc_id = result["document_id"]
        filename = result["filename"]
        page = result.get("page")
        snippet = text[:300] + ("..." if len(text) > 300 else "")

        context_parts.append(
            f"[Source {i+1}: {filename}]\n{text}"
        )
        sources.append(Source(
            document_id=doc_id,
            filename=filename,
            page=page,
            text_snippet=snippet,
        ))

    context = "\n\n---\n\n".join(context_parts)
    prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

    # Step 4: Generate answer
    answer = bedrock_service.generate_answer(prompt)

    return {
        "answer": answer,
        "sources": sources,
    }
