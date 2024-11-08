import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from utils.db_utils import PostgresClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
db_client = PostgresClient()


@app.get("/")
def hello_world():
    return {"message": "AWS - Hello World"}


@app.get("/db/health", status_code=200)
def database_health_check():
    """
    Endpoint to check database connection health

    Returns:
        dict: Health status of the database connection
    """
    try:
        # Attempt to connect to the database
        with db_client.engine.connect() as connection:
            # Use a parameterized query for best practices
            connection.execute(text("SELECT 1"))
            logger.info("Database health check successful")
            return {"status": "healthy", "message": "Database connection successful"}
    except OperationalError as e:
        # Specific handling for connection-related errors
        error_msg = f"Database connection failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=503, detail=error_msg)
    except SQLAlchemyError as e:
        # Catch any other SQLAlchemy-related errors
        error_msg = f"Database error: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        # Catch any unexpected exceptions
        error_msg = f"Database health check error: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
