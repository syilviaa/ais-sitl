"""
Database configuration and initialization.

Supports PostgreSQL with SQLAlchemy ORM for Veha 5 multi-drone support.
"""

import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Base class for all ORM models
Base = declarative_base()


def _normalize_database_url(url: str) -> str:
    """Render provides postgres:// URLs; SQLAlchemy expects postgresql://."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Database:
    """Database connection and session management."""

    def __init__(self, database_url: str, echo: bool = False):
        """Initialize database connection."""
        self.database_url = database_url
        self.echo = echo
        self.engine = None
        self.SessionLocal = None

    def initialize(self):
        """Create engine and session factory."""
        try:
            logger.info("Connecting to database")

            connect_args = {}
            engine_kwargs = {
                "echo": self.echo,
                "pool_pre_ping": True,
            }

            if self.database_url.startswith("sqlite"):
                engine_kwargs["connect_args"] = {"check_same_thread": False}
            else:
                engine_kwargs.update(
                    {
                        "poolclass": QueuePool,
                        "pool_size": 10,
                        "max_overflow": 20,
                    }
                )

            self.engine = create_engine(self.database_url, **engine_kwargs)

            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")

            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
            )

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    def create_all_tables(self):
        """Create all tables from models."""
        try:
            # Import models so they register with Base.metadata
            import src.backend.models  # noqa: F401

            Base.metadata.create_all(bind=self.engine, checkfirst=True)
            logger.info("All database tables created")
        except Exception as e:
            # Concurrent gunicorn workers may race on first deploy
            if "already exists" in str(e).lower():
                logger.info("Database tables already exist")
                return
            logger.error(f"Table creation failed: {e}")
            raise

    def get_session(self):
        """Get new database session."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()

    def close(self):
        """Close all connections."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")


# Global database instance
db = Database(
    database_url=_normalize_database_url(
        os.getenv("DATABASE_URL", "sqlite:///./ais_sitl.db")
    ),
    echo=os.getenv("SQLALCHEMY_ECHO", "False").lower() == "true",
)

# Session factory exported for services (initialized in init_db)
SessionLocal = None


def init_db():
    """Initialize database engine, session factory, and tables."""
    global SessionLocal

    if SessionLocal is not None:
        return SessionLocal

    db.initialize()
    db.create_all_tables()
    SessionLocal = db.SessionLocal
    return SessionLocal
