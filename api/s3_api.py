import uuid
from io import BytesIO
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, File, HTTPException, UploadFile

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
    if not bucket_name.replace("-", "").isalnum():
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


@app.post("/buckets/create", status_code=201)
async def create_bucket(
    bucket_name: Optional[str] = None, region: Optional[str] = "us-east-1"
):
    """
    Create a new S3 bucket

    Args:
        bucket_name: Name of the bucket to create (optional, will generate if not provided)
        region: AWS region where the bucket should be created (default: us-east-1)

    Returns:
        dict: Information about the created bucket
    """
    s3_client = boto3.client("s3")

    # Generate bucket name if not provided
    if not bucket_name:
        bucket_name = f"bucket-{uuid.uuid4().hex[:8]}"

    # Validate bucket name
    if not validate_bucket_name(bucket_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid bucket name. Must be 3-63 characters, lowercase, alphanumeric or hyphens.",
        )

    try:
        # Create bucket
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            location = {"LocationConstraint": region}
            s3_client.create_bucket(
                Bucket=bucket_name, CreateBucketConfiguration=location
            )

        return {
            "message": "Bucket created successfully",
            "bucket_name": bucket_name,
            "region": region,
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
