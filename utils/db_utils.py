import os
import ssl
from contextlib import contextmanager
from typing import Any, Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

load_dotenv()


class PostgresClient:
    """Utility class for PostgreSQL database operations"""

    def __init__(self):
        """Initialize database connection"""
        # Load environment variables
        load_dotenv()

        # Get database URL from environment variable
        url = os.getenv("POSTGRES_URL")

        # Ensure URL uses correct dialect
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)

        self.connection_url = url
        if not self.connection_url:
            raise ValueError(
                "Database connection URL not found in environment variables"
            )

        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with proper configuration"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        return create_engine(
            self.connection_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={"ssl": ssl_context},
        )

    @contextmanager
    def get_session(self) -> Generator:
        """
        Get database session with automatic cleanup

        Yields:
            Session: Database session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def execute_query(self, query: str, params: dict = None) -> list[dict[str, Any]]:
        """
        Execute a raw SQL query

        Args:
            query (str): SQL query string
            params (dict, optional): Query parameters

        Returns:
            list[dict[str, Any]]: Query results
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(query), params or {})
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            raise

    def execute_transaction(self, queries: list[tuple[str, dict]]) -> bool:
        """
        Execute multiple queries in a transaction

        Args:
            queries (list[tuple[str, dict]]): List of (query, params) tuples

        Returns:
            bool: True if transaction successful
        """
        try:
            with self.get_session() as session:
                for query, params in queries:
                    session.execute(text(query), params or {})
                return True
        except SQLAlchemyError as e:
            print(f"Transaction error: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check database connection health by querying the products table

        Returns:
            bool: True if connection is healthy and products exist, else False
        """
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT * FROM products"))
                products = result.fetchall()
                if products:
                    print("Products found in the database.")
                    return True
                else:
                    print("No products found in the database.")
                    return False
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return False
