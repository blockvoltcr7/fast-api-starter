from fastapi import FastAPI, HTTPException
from typing import Optional
import boto3
from botocore.exceptions import ClientError

app = FastAPI(title="S3 Bucket API")

@app.post("/buckets/", status_code=201)
async def create_bucket(bucket_name: str, region: Optional[str] = "us-east-1"):
    """
    Create a new S3 bucket
    
    Args:
        bucket_name: Name of the bucket to create
        region: AWS region where the bucket should be created (default: us-east-1)
    
    Returns:
        dict: Information about the created bucket
    """
    s3_client = boto3.client('s3')
    
    try:
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            location = {'LocationConstraint': region}
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration=location
            )
            
        return {
            "message": "Bucket created successfully",
            "bucket_name": bucket_name,
            "region": region
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'BucketAlreadyExists':
            raise HTTPException(
                status_code=409,
                detail=f"Bucket {bucket_name} already exists"
            )
        elif error_code == 'BucketAlreadyOwnedByYou':
            raise HTTPException(
                status_code=409,
                detail=f"Bucket {bucket_name} already owned by you"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )
