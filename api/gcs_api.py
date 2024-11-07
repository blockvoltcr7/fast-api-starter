import os

from fastapi import FastAPI, HTTPException

from utils.gcs_utils import GCSClient

app = FastAPI(title="GCS Bucket API")

# Get project ID from environment variable or use default
gcs_client = GCSClient("rflkt-441001")


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to GCS Bucket API"}


@app.get("/bucket/create/{bucket_name}")
async def create_bucket(bucket_name: str):
    """Create a new GCS bucket with the given name"""
    try:
        bucket = gcs_client.create_bucket(bucket_name)
        if bucket:
            return {
                "message": f"Bucket {bucket_name} created successfully",
                "bucket_name": bucket_name,
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create bucket")
    except Exception as e:
        error_msg = str(e)
        if "storage.buckets.create access" in error_msg:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: You don't have access to create buckets. Please check your GCP credentials and permissions.",
            )
        raise HTTPException(status_code=500, detail=error_msg)
