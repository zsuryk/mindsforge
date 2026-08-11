from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    return create_engine(
        get_settings().DATABASE_URL,
        connect_args={"check_same_thread": False},
    )


def init_db() -> None:
    from app.models import job  # noqa: F401  register models with Base metadata

    Base.metadata.create_all(get_engine())


def get_db() -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()