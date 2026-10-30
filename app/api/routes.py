from fastapi import APIRouter

from app.api import auth, documents, query

router = APIRouter()

router.include_router(auth.router)
router.include_router(documents.router)
router.include_router(query.router)