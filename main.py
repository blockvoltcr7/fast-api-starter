import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from utils.db_utils import PostgresClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
db_client = PostgresClient()


@app.get("/")
async def hello_world():
    return {"message": "AWS - Hello World"}


@app.get("/db/health", status_code=200)
async def database_health_check():
    """
    Endpoint to check database connection health

    Returns:
        dict: Health status of the database connection
    """
    try:
        # Attempt to connect to the database
        with db_client.engine.connect() as connection:
            # Execute a simple query to check the connection
            connection.execute("SELECT 1")
            logger.info("Database health check successful")
            return {"status": "healthy", "message": "Database connection successful"}
    except SQLAlchemyError as e:
        error_msg = f"Database connection failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=503, detail=error_msg)
    except Exception as e:
        error_msg = f"Database health check error: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=503, detail=error_msg)
