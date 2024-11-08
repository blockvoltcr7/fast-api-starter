import logging
import os
from typing import Any, List, Optional, Tuple

import pg8000.native
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgresClient:
    """Utility class for PostgreSQL database operations using pg8000"""

    def __init__(self):
        """Initialize database connection configuration"""
        url = os.getenv("POSTGRES_URL")
        print(url)
        if not url:
            raise ValueError(
                "Database connection URL not found in environment variables"
            )

        # Parse connection URL
        url_parts = url.replace("postgres://", "").split("@")
        user_pass = url_parts[0].split(":")
        host_port_db = url_parts[1].split("/")
        host_port = host_port_db[0].split(":")

        self.config = {
            "user": user_pass[0],
            "password": user_pass[1],
            "host": host_port[0],
            "port": int(host_port[1]),
            "database": host_port_db[1].split("?")[0],
            "ssl_context": True,
        }
        self.conn = None

    def connect(self) -> Tuple[bool, Optional[str]]:
        """
        Establishes a connection to the PostgreSQL database.
        Returns: Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            self.conn = pg8000.native.Connection(**self.config)
            return True, None
        except Exception as e:
            error_msg = f"Error connecting to PostgreSQL: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def execute_query(self, query: str, params: tuple = ()) -> List[tuple]:
        """
        Execute a SQL query

        Args:
            query (str): SQL query string
            params (tuple): Query parameters

        Returns:
            List[tuple]: Query results
        """
        if not self.conn:
            success, error = self.connect()
            if not success:
                raise Exception(f"Failed to connect to database: {error}")

        try:
            return self.conn.run(query, params)
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise

    def execute_transaction(self, queries: List[Tuple[str, tuple]]) -> bool:
        """
        Execute multiple queries in a transaction

        Args:
            queries (List[Tuple[str, tuple]]): List of (query, params) tuples

        Returns:
            bool: True if transaction successful
        """
        if not self.conn:
            success, error = self.connect()
            if not success:
                return False

        try:
            with self.conn.transaction():
                for query, params in queries:
                    self.conn.run(query, params)
            return True
        except Exception as e:
            logger.error(f"Transaction error: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check database connection health

        Returns:
            bool: True if connection is healthy
        """
        try:
            if not self.conn:
                success, error = self.connect()
                if not success:
                    return False

            self.conn.run("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def create_table(self, table_name: str, columns: List[str]) -> bool:
        """
        Create a new table in the database

        Args:
            table_name (str): Name of the table to create
            columns (List[str]): List of column definitions

        Returns:
            bool: True if table creation was successful
        """
        try:
            # Construct CREATE TABLE query
            columns_str = ", ".join(columns)
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_str})"
            
            self.execute_query(query)
            logger.info(f"Table {table_name} created successfully")
            return True
        except Exception as e:
            logger.error(f"Error creating table {table_name}: {e}")
            return False

    def drop_table(self, table_name: str, cascade: bool = False) -> bool:
        """
        Drop an existing table from the database

        Args:
            table_name (str): Name of the table to drop
            cascade (bool, optional): Whether to drop dependent objects. Defaults to False.

        Returns:
            bool: True if table deletion was successful
        """
        try:
            # Construct DROP TABLE query
            query = f"DROP TABLE IF EXISTS {table_name}"
            if cascade:
                query += " CASCADE"
            
            self.execute_query(query)
            logger.info(f"Table {table_name} dropped successfully")
            return True
        except Exception as e:
            logger.error(f"Error dropping table {table_name}: {e}")
            return False

    def update_table(self, table_name: str, set_clause: str, where_clause: Optional[str] = None) -> int:
        """
        Update records in a table

        Args:
            table_name (str): Name of the table to update
            set_clause (str): SET clause of the UPDATE statement
            where_clause (Optional[str], optional): WHERE clause to filter updates. Defaults to None.

        Returns:
            int: Number of rows affected
        """
        try:
            # Construct UPDATE query
            query = f"UPDATE {table_name} SET {set_clause}"
            if where_clause:
                query += f" WHERE {where_clause}"
            
            result = self.execute_query(query)
            logger.info(f"Updated records in {table_name}")
            return len(result)
        except Exception as e:
            logger.error(f"Error updating table {table_name}: {e}")
            return 0

    def insert_record(self, table_name: str, columns: List[str], values: List[Any]) -> bool:
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
            placeholders = ", ".join(["%s"] * len(values))
            query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            
            self.execute_query(query, tuple(values))
            logger.info(f"Record inserted into {table_name}")
            return True
        except Exception as e:
            logger.error(f"Error inserting record into {table_name}: {e}")
            return False

    def get_table_info(self, table_name: str) -> List[Tuple[str, str]]:
        """
        Retrieve column information for a given table

        Args:
            table_name (str): Name of the table

        Returns:
            List[Tuple[str, str]]: List of (column_name, data_type) tuples
        """
        try:
            query = """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = %s
            """
            result = self.execute_query(query, (table_name,))
            return result
        except Exception as e:
            logger.error(f"Error retrieving table info for {table_name}: {e}")
            return []

    def count_records(self, table_name: str, where_clause: Optional[str] = None) -> int:
        """
        Count the number of records in a table

        Args:
            table_name (str): Name of the table
            where_clause (Optional[str], optional): WHERE clause to filter counting. Defaults to None.

        Returns:
            int: Number of records
        """
        try:
            query = f"SELECT COUNT(*) FROM {table_name}"
            if where_clause:
                query += f" WHERE {where_clause}"
            
            result = self.execute_query(query)
            return result[0][0]
        except Exception as e:
            logger.error(f"Error counting records in {table_name}: {e}")
            return 0
