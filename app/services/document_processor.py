import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.db import Document, DocumentStatus
from app.services import bedrock as bedrock_service
from app.services import s3 as s3_service
from app.services.vector_store import VectorStore
from app.utils.chunker import chunk_text
from app.utils.text_extractor import extract_text

logger = logging.getLogger(__name__)
settings = get_settings()


def process_document(document_id: str, user_id: str, db: Session):
    """
    Full document processing pipeline (runs as a background task):
    1. Fetch document metadata from DB
    2. Download file from S3
    3. Extract text (PDF / DOCX / TXT)
    4. Chunk the text
    5. Generate embeddings via Bedrock
    6. Store embeddings in per-user FAISS index
    7. Update document status to READY
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        logger.error("Document %s not found in DB", document_id)
        return

    # Mark as processing
    doc.status = DocumentStatus.PROCESSING
    db.commit()
    logger.info("Processing document %s (%s)", document_id, doc.original_filename)

    try:
        # Step 1: Download from S3
        file_bytes = s3_service.download_file(doc.s3_key)
        if file_bytes is None:
            raise RuntimeError(f"Could not download file from S3 key: {doc.s3_key}")

        # Step 2: Extract text
        text, page_count = extract_text(file_bytes, doc.original_filename)
        if not text.strip():
            raise RuntimeError("No text could be extracted from the document")

        # Step 3: Chunk the text
        chunks = chunk_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        if not chunks:
            raise RuntimeError("Text chunking produced no chunks")

        logger.info("Document %s: %d pages, %d chunks", document_id, page_count, len(chunks))

        # Step 4: Generate embeddings
        embeddings = []
        for chunk in chunks:
            emb = bedrock_service.generate_embeddings(chunk)
            if emb is None:
                raise RuntimeError("Embedding generation returned None")
            embeddings.append(emb)

        # Step 5: Store in FAISS
        store = VectorStore(user_id=user_id, index_dir=settings.FAISS_INDEX_DIR)
        store.add_chunks(
            embeddings=embeddings,
            chunks=chunks,
            document_id=document_id,
            filename=doc.original_filename,
        )

        # Step 6: Update DB
        doc.status = DocumentStatus.READY
        doc.page_count = page_count
        doc.chunk_count = len(chunks)
        doc.processed_at = datetime.now(timezone.utc)
        doc.error_message = None
        db.commit()
        logger.info("Document %s processing complete", document_id)

    except Exception as exc:
        logger.error("Document %s processing failed: %s", document_id, exc, exc_info=True)
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(exc)[:500]
        db.commit()
