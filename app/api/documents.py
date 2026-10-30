import os
import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models.db import Document, DocumentStatus, get_db, User
from app.models.schemas import DocumentDetail, DocumentList, DocumentOut
from app.services import document_processor, s3 as s3_service
from app.utils.text_extractor import ALLOWED_EXTENSIONS, MIME_MAP, get_file_extension

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()

MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # bytes


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a PDF, DOCX, or TXT document for processing."""
    # Validate file extension
    ext = get_file_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file
    file_bytes = await file.read()

    # Validate file size
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum allowed size is {settings.MAX_FILE_SIZE_MB} MB.",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Build S3 key: users/{user_id}/documents/{doc_id}_{filename}
    doc_id = str(uuid.uuid4())
    safe_filename = os.path.basename(file.filename or "document")
    s3_key = f"users/{current_user.id}/documents/{doc_id}_{safe_filename}"

    # Upload to S3
    success = s3_service.upload_file(file_bytes, s3_key, MIME_MAP.get(ext, "application/octet-stream"))
    if not success:
        logger.warning("S3 upload failed for %s – storing metadata without S3 key", s3_key)
        s3_key_stored = None
    else:
        s3_key_stored = s3_key

    # Create DB record
    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=f"{doc_id}_{safe_filename}",
        original_filename=safe_filename,
        s3_key=s3_key_stored or s3_key,
        file_size=len(file_bytes),
        file_type=ext,
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Trigger background processing
    # We pass a new db session because BackgroundTasks outlive the request
    from app.models.db import SessionLocal
    def _process():
        bg_db = SessionLocal()
        try:
            document_processor.process_document(doc_id, current_user.id, bg_db)
        finally:
            bg_db.close()

    background_tasks.add_task(_process)
    return doc


@router.get("", response_model=DocumentList)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all documents belonging to the current user."""
    docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return DocumentList(documents=docs, total=len(docs))


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details for a specific document, including a temporary download URL."""
    doc = _get_user_document(document_id, current_user.id, db)
    download_url = s3_service.get_presigned_url(doc.s3_key) if doc.s3_key else None
    detail = DocumentDetail.model_validate(doc)
    detail.download_url = download_url
    return detail


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document from S3, vector store, and the database."""
    doc = _get_user_document(document_id, current_user.id, db)

    # Delete from S3
    if doc.s3_key:
        s3_service.delete_file(doc.s3_key)

    # Remove from FAISS vector store
    try:
        from app.services.vector_store import VectorStore
        store = VectorStore(user_id=current_user.id, index_dir=settings.FAISS_INDEX_DIR)
        store.delete_document(document_id)
    except Exception as e:
        logger.warning("Could not remove document %s from vector store: %s", document_id, e)

    # Delete from DB
    db.delete(doc)
    db.commit()


def _get_user_document(document_id: str, user_id: str, db: Session) -> Document:
    """Helper: fetch a document enforcing ownership. Raises 404/403 as appropriate."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return doc
