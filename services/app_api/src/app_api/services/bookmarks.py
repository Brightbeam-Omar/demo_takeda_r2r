"""A user's bookmarked row keys (F16-FR-04)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app_api.models import Bookmark


def bookmarked_keys(session: Session, user_key: str) -> list[str]:
    return sorted(session.scalars(select(Bookmark.row_key).where(Bookmark.user_key == user_key)))
