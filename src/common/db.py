from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from src.common.config import settings
from src.common.models import Base

_engine_cache = {}
_session_cache = {}


def get_engine(db_url: str = None):
    url = db_url or settings.database_url
    if url not in _engine_cache:
        if url.startswith("sqlite"):
            _engine_cache[url] = create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            _engine_cache[url] = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)
        _session_cache[url] = sessionmaker(autocommit=False, autoflush=False, bind=_engine_cache[url])
    return _engine_cache[url]


def get_session(db_url: str = None) -> Session:
    url = db_url or settings.database_url
    get_engine(url)
    return _session_cache[url]()


def init_db(db_url: str = None) -> None:
    """Create all tables in the target database."""
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)


@contextmanager
def db_session_scope(db_url: str = None) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = get_session(db_url)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
