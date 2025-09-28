# api/models.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base used by Alembic for autogenerate."""
    pass
