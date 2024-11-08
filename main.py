from fastapi import FastAPI, HTTPException
from utils.db_utils import PostgresClient

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
    if db_client.health_check():
        return {"status": "healthy", "message": "Database connection successful"}
    else:
        raise HTTPException(status_code=503, detail="Database connection failed")
