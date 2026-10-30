from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.db import Document, DocumentStatus, get_db, User
from app.models.schemas import QueryRequest, QueryResponse
from app.services import rag as rag_service

router = APIRouter(prefix="/query", tags=["AI Query"])


@router.post("", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ask a question about uploaded documents using RAG + AWS Bedrock.
    Optionally filter to specific document IDs.
    """
    # Validate that requested document_ids belong to this user
    if request.document_ids:
        user_doc_ids = {
            str(d.id)
            for d in db.query(Document.id)
            .filter(
                Document.user_id == current_user.id,
                Document.status == DocumentStatus.READY,
            )
            .all()
        }
        invalid = set(request.document_ids) - user_doc_ids
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Documents not found or not ready: {', '.join(invalid)}",
            )

    result = rag_service.answer_question(
        user_id=current_user.id,
        question=request.question,
        document_ids=request.document_ids,
    )

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
    )
