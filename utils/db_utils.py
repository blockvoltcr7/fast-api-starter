import logging
import os
from typing import Any, List, Tuple

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgresClient:
    """Utility class for PostgreSQL database operations using SQLAlchemy"""

    def __init__(self):
        """Initialize database connection configuration"""
        url = os.getenv("POSTGRES_PSYCOPG2_URL")

        if not url:
            raise ValueError(
                "Database connection URL not found in environment variables"
            )

        # Create SQLAlchemy engine with connection pool settings
        self.engine = create_engine(
            url,
            pool_pre_ping=True,  # Test connection before using
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False,  # Set to True for SQL logging
        )
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = MetaData()

        # Perform an initial connection test
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                logger.info("Database connection successful")
        except OperationalError as e:
            logger.error(f"Database connection error: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid connection URL: {e}")
            raise

    def execute_query(self, query: str, params: dict = {}) -> List[tuple]:
        """
        Execute a SQL query with parameter binding

        Args:
            query (str): SQL query string
            params (dict): Query parameters

        Returns:
            List[tuple]: Query results
        """
        session = self.Session()
        try:
            result = session.execute(text(query), params)
            session.commit()  # Commit the transaction if it's a modifying query
            return result.fetchall()
        except SQLAlchemyError as e:
            session.rollback()  # Rollback in case of error
            logger.error(f"Query execution error: {e}")
            raise
        finally:
            session.close()

    def insert_record(
        self, table_name: str, columns: List[str], values: List[Any]
    ) -> bool:
        """
        Insert a new record into a table with parameter binding

        Args:
            table_name (str): Name of the table
            columns (List[str]): List of column names
            values (List[Any]): List of values to insert

        Returns:
            bool: True if insertion was successful
        """
        # Construct INSERT query using named placeholders
        columns_str = ", ".join(columns)
        placeholders = ", ".join([f":{col}" for col in columns])
        query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

        # Bind column names to values as a dictionary
        params = {col: val for col, val in zip(columns, values)}

        try:
            # Use session explicitly for better transaction control
            session = self.Session()
            session.execute(text(query), params)
            session.commit()
            logger.info(f"Record inserted into {table_name}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error inserting record into {table_name}: {e}")
            return False
        finally:
            session.close()

    # Add other methods as needed, using the same pattern for session management
