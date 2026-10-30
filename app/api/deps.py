from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.models.db import get_db, User


async def get_current_user(
    token_payload: dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current authenticated user from the JWT payload."""
    user_id: str = token_payload.get("sub")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
