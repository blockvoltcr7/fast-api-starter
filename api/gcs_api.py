from fastapi import FastAPI, HTTPException
from utils.gcs_utils import GCSClient

app = FastAPI()
gcs_client = GCSClient()

@app.get("/bucket/create/{bucket_name}")
async def create_bucket(bucket_name: str):
    """Create a new GCS bucket with the given name"""
    try:
        bucket = gcs_client.create_bucket(bucket_name)
        if bucket:
            return {"message": f"Bucket {bucket_name} created successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to create bucket")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
