from typing import List, Optional, Dict, Any
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, UploadFile, File
import uuid

app = FastAPI(title="S3 Bucket API")

def validate_bucket_name(bucket_name: str) -> bool:
    """
    Validate S3 bucket name according to AWS rules
    
    Args:
        bucket_name (str): Proposed bucket name
    
    Returns:
        bool: Whether the bucket name is valid
    """
    # AWS bucket name rules
    if not 3 <= len(bucket_name) <= 63:
        return False
    if not bucket_name.islower():
        return False
    if not bucket_name.replace('-', '').isalnum():
        return False
    return True

@app.get("/buckets/", status_code=200)
async def list_buckets():
    """
    List all S3 buckets

    Returns:
        dict: List of all buckets
    """
    s3_client = boto3.client("s3")

    try:
        response = s3_client.list_buckets()
        buckets = [bucket["Name"] for bucket in response["Buckets"]]
        return {"buckets": buckets}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/buckets/create-with-object", status_code=201)
async def create_bucket_with_object(
    bucket_name: Optional[str] = None, 
    region: Optional[str] = "us-east-1", 
    file: UploadFile = File(...),
    object_key: Optional[str] = None
):
    """
    Create a new S3 bucket and upload an object in a single operation

    Args:
        bucket_name: Name of the bucket to create (optional, will generate if not provided)
        region: AWS region where the bucket should be created (default: us-east-1)
        file: File to upload to the bucket
        object_key: Optional custom object key (will generate if not provided)

    Returns:
        dict: Information about the created bucket and uploaded object
    """
    s3_client = boto3.client("s3")

    # Generate bucket name if not provided
    if not bucket_name:
        bucket_name = f"bucket-{uuid.uuid4().hex[:8]}"
    
    # Validate bucket name
    if not validate_bucket_name(bucket_name):
        raise HTTPException(
            status_code=400, 
            detail="Invalid bucket name. Must be 3-63 characters, lowercase, alphanumeric or hyphens."
        )

    # Generate object key if not provided
    if not object_key:
        object_key = f"uploads/{uuid.uuid4().hex}"

    try:
        # Create bucket
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            location = {"LocationConstraint": region}
            s3_client.create_bucket(
                Bucket=bucket_name, CreateBucketConfiguration=location
            )

        # Upload file
        file_content = await file.read()
        s3_client.put_object(
            Bucket=bucket_name, 
            Key=object_key, 
            Body=file_content,
            ContentType=file.content_type
        )

        return {
            "message": "Bucket created and object uploaded successfully",
            "bucket_name": bucket_name,
            "region": region,
            "object_key": object_key,
            "file_details": {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(file_content)
            }
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "BucketAlreadyExists":
            raise HTTPException(
                status_code=409, detail=f"Bucket {bucket_name} already exists"
            )
        elif error_code == "BucketAlreadyOwnedByYou":
            raise HTTPException(
                status_code=409, detail=f"Bucket {bucket_name} already owned by you"
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))
