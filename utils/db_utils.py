import os
from typing import Any, Optional, Tuple, List
from dotenv import load_dotenv
import pg8000.native

load_dotenv()


class PostgresClient:
    """Utility class for PostgreSQL database operations using pg8000"""

    def __init__(self):
        """Initialize database connection configuration"""
        url = os.getenv("POSTGRES_URL")
        if not url:
            raise ValueError("Database connection URL not found in environment variables")

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
            "ssl": True,
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
            return False, f"Error connecting to PostgreSQL: {str(e)}"

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
            print(f"Query execution error: {e}")
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
            print(f"Transaction error: {e}")
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
            print(f"Health check failed: {e}")
            return False

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
