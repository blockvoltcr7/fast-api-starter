import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine
from contextlib import contextmanager
from typing import Generator, Any
from dotenv import load_dotenv
import ssl

load_dotenv()

class PostgresClient:
    """Utility class for PostgreSQL database operations"""
    
    def __init__(self):
        """Initialize database connection"""
        self.connection_url = f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DATABASE')}?sslmode=require"
        if not self.connection_url:
            raise ValueError("Database connection URL not found in environment variables")
        
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with proper configuration"""
        # Create an SSL context to handle SSL connections
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        return create_engine(
            self.connection_url,
            pool_pre_ping=True,  # Enable connection health checks
            pool_size=5,         # Maximum number of connections in pool
            max_overflow=10,     # Maximum number of connections that can be created beyond pool_size
            pool_timeout=30,     # Timeout for getting connection from pool
            pool_recycle=1800,   # Recycle connections after 30 minutes
            connect_args={'ssl': ssl_context}  # Add SSL context for secure connections
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
        Check database connection health
        
        Returns:
            bool: True if connection is healthy
        """
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except SQLAlchemyError:
            return False
