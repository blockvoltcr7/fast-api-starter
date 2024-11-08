import logging
from fastapi import FastAPI, HTTPException
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
        success, error = db_client.connect()
        if success:
            if db_client.health_check():
                logger.info("Database health check successful")
                return {"status": "healthy", "message": "Database connection successful"}
        
        error_msg = error if error else "Database connection failed"
        logger.error(f"Health check failed: {error_msg}")
        raise HTTPException(status_code=503, detail=error_msg)
    except Exception as e:
        error_msg = f"Database health check error: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=503, detail=error_msg)
