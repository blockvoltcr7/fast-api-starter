import logging
import os
from typing import Any, List, Tuple

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgresClient:
    """Utility class for PostgreSQL database operations using SQLAlchemy"""

    def __init__(self):
        """Initialize database connection configuration"""
        url = os.getenv("POSTGRES_URL")
        if not url:
            raise ValueError(
                "Database connection URL not found in environment variables"
            )

        try:
            # Create SQLAlchemy engine with additional connection parameters
            self.engine = create_engine(
                url, 
                pool_pre_ping=True,  # Test connection before using
                pool_recycle=3600,   # Recycle connections after 1 hour
                echo=False           # Set to True for SQL logging
            )
            self.Session = sessionmaker(bind=self.engine)
            self.metadata = MetaData()

            # Perform an initial connection test
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                logger.info("Database connection successful")
        except (ValueError, OperationalError) as e:
            logger.error(f"Database connection error: {e}")
            raise

    def execute_query(self, query: str, params: dict = {}) -> List[tuple]:
        """
        Execute a SQL query

        Args:
            query (str): SQL query string
            params (dict): Query parameters

        Returns:
            List[tuple]: Query results
        """
        session = self.Session()
        try:
            result = session.execute(text(query), params)
            session.commit()
            return result.fetchall()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Query execution error: {e}")
            raise
        finally:
            session.close()

    def insert_record(
        self, table_name: str, columns: List[str], values: List[Any]
    ) -> bool:
        """
        Insert a new record into a table

        Args:
            table_name (str): Name of the table
            columns (List[str]): List of column names
            values (List[Any]): List of values to insert

        Returns:
            bool: True if insertion was successful
        """
        try:
            # Construct INSERT query
            columns_str = ", ".join(columns)
            placeholders = ", ".join([f":{col}" for col in columns])
            query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

            params = {col: val for col, val in zip(columns, values)}
            self.execute_query(query, params)
            logger.info(f"Record inserted into {table_name}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error inserting record into {table_name}: {e}")
            return False

    # Add other methods as needed, using the same pattern for session management
