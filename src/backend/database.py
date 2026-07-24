"""
Database configuration and initialization.

Supports PostgreSQL with SQLAlchemy ORM for Veha 5 multi-drone support.
"""

import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Base class for all ORM models
Base = declarative_base()


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
            logger.info(f"Connecting to database: {self.database_url}")

            self.engine = create_engine(
                self.database_url,
                echo=self.echo,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,  # Test connections
            )

            # Test connection
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")
            logger.info("✅ Database connection successful")

            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
            )

        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise

    def create_all_tables(self):
        """Create all tables from models."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ All tables created")
        except Exception as e:
            logger.error(f"❌ Table creation failed: {e}")
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
            logger.info("✅ Database connections closed")


# Global database instance
db = Database(
    database_url="sqlite:///./ais_sitl.db",  # SQLite for dev
    echo=False,
)
