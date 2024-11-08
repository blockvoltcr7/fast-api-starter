import uvicorn
from fastapi import FastAPI
from api.s3_api import app as s3_api

app = FastAPI()

# Include the S3 API router
app.include_router(s3_api)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
