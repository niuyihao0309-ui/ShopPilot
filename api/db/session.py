from collections.abc import Generator  # noqa: I001

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.app.core.config import get_settings


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




