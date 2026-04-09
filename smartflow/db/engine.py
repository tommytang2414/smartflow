from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from smartflow.config import DB_URL
from smartflow.db.models import Base

engine = create_engine(DB_URL, echo=False)
Session = sessionmaker(bind=engine)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session():
    """Get a new DB session."""
    return Session()
