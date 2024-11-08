import uuid
from datetime import timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordRequestForm

from auth.jwt_auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
    get_current_user,
)

app = APIRouter(prefix="", tags=["s3"])


@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Generate JWT access token for authentication.

    Args:
        form_data (OAuth2PasswordRequestForm): The form data containing username and password.

    Returns:
        dict: A dictionary containing the access token and token type.

    Raises:
        HTTPException: If authentication fails, a 400 error is raised.
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


def validate_bucket_name(bucket_name: str) -> bool:
    """
    Validate S3 bucket name according to AWS rules.

    Args:
        bucket_name (str): Proposed bucket name.

    Returns:
        bool: Whether the bucket name is valid.
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
async def list_buckets(current_user: dict = Depends(get_current_user)):
    """
    List all S3 buckets.

    Args:
        current_user (dict): The current authenticated user.

    Returns:
        dict: A dictionary containing a list of all bucket names.

    Raises:
        HTTPException: If there is an error retrieving the bucket list, a 500 error is raised.
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
    bucket_name: Optional[str] = None,
    region: Optional[str] = "us-east-1",
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new S3 bucket.

    Args:
        bucket_name (Optional[str]): Name of the bucket to create (optional, will generate if not provided).
        region (Optional[str]): AWS region where the bucket should be created (default: us-east-1).

    Returns:
        dict: Information about the created bucket.

    Raises:
        HTTPException: If the bucket name is invalid or if there is an error creating the bucket.
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


@app.get("/buckets/{bucket_name}", status_code=200)
async def get_bucket(bucket_name: str, current_user: dict = Depends(get_current_user)):
    """
    Get information about a specific S3 bucket.

    Args:
        bucket_name (str): Name of the bucket to retrieve.
        current_user (dict): The current authenticated user.

    Returns:
        dict: Information about the specified bucket.

    Raises:
        HTTPException: If the bucket name is invalid or if the bucket does not exist.
    """
    s3_client = boto3.client("s3")

    # Validate bucket name
    if not validate_bucket_name(bucket_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid bucket name. Must be 3-63 characters, lowercase, alphanumeric or hyphens.",
        )

    try:
        # Check if bucket exists by attempting to get its location
        location = s3_client.get_bucket_location(Bucket=bucket_name)

        return {
            "message": "Bucket found successfully",
            "bucket_name": bucket_name,
            "region": location["LocationConstraint"] or "us-east-1",
        }
    except s3_client.exceptions.NoSuchBucket:
        raise HTTPException(
            status_code=404, detail=f"Bucket {bucket_name} does not exist"
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDenied":
            raise HTTPException(
                status_code=403, detail=f"Access denied for bucket {bucket_name}"
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/buckets/create-with-folder", status_code=201)
async def create_bucket_with_folder(
    bucket_name: Optional[str] = None,
    region: Optional[str] = "us-east-1",
    folder_name: Optional[str] = "new-folder/",
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new S3 bucket with an initial folder.

    Args:
        bucket_name (Optional[str]): Name of the bucket to create (optional, will generate if not provided).
        region (Optional[str]): AWS region where the bucket should be created (default: us-east-1).
        folder_name (Optional[str]): Name of the initial folder to create (default: 'new-folder/').

    Returns:
        dict: Information about the created bucket and folder.

    Raises:
        HTTPException: If the bucket name is invalid or if there is an error creating the bucket or folder.
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

        # Create an empty folder (using a zero-byte object with a trailing slash)
        s3_client.put_object(Bucket=bucket_name, Key=folder_name, Body=b"")

        return {
            "message": "Bucket and folder created successfully",
            "bucket_name": bucket_name,
            "region": region,
            "folder_name": folder_name,
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


@app.get("/buckets/{bucket_name}/folders/{folder_name}/contents", status_code=200)
async def get_folder_contents(
    bucket_name: str,
    folder_name: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get the contents of a specific folder in an S3 bucket.

    Args:
        bucket_name (str): Name of the S3 bucket.
        folder_name (str): Path to the folder within the bucket (e.g., 'my-folder/').
        current_user (dict): The current authenticated user.

    Returns:
        dict: A list of objects within the specified folder.

    Raises:
        HTTPException: If the bucket name is invalid, the bucket does not exist, or if access is denied.
    """
    s3_client = boto3.client("s3")

    # Validate bucket name
    if not validate_bucket_name(bucket_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid bucket name. Must be 3-63 characters, lowercase, alphanumeric or hyphens.",
        )

    # Ensure folder name ends with a trailing slash
    if not folder_name.endswith("/"):
        folder_name += "/"

    try:
        # List objects in the specified folder
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=folder_name)

        if "Contents" not in response:
            return {"message": "Folder is empty or does not exist", "objects": []}

        # Extract object keys within the folder
        objects = [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            }
            for obj in response["Contents"]
        ]

        return {
            "message": "Folder contents retrieved successfully",
            "bucket_name": bucket_name,
            "folder_name": folder_name,
            "objects": objects,
        }

    except s3_client.exceptions.NoSuchBucket:
        raise HTTPException(
            status_code=404, detail=f"Bucket {bucket_name} does not exist"
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDenied":
            raise HTTPException(
                status_code=403, detail=f"Access denied for bucket {bucket_name}"
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/buckets/{bucket_name}/folders", status_code=200)
async def list_bucket_folders(
    bucket_name: str,
    current_user: dict = Depends(get_current_user),
):
    """
    List top-level folders in a specific S3 bucket.

    Args:
        bucket_name (str): The name of the S3 bucket to list folders from.
        current_user (dict): The current authenticated user, automatically provided by FastAPI's dependency injection.

    Returns:
        dict: A dictionary containing:
            - message (str): A message indicating the result of the operation.
            - bucket_name (str): The name of the bucket.
            - folders (list): A list of folder names in the specified bucket. If no folders are found, an empty list is returned.

    Raises:
        HTTPException: Raises a 400 error if the bucket name is invalid.
        HTTPException: Raises a 404 error if the specified bucket does not exist.
        HTTPException: Raises a 403 error if access to the bucket is denied.
        HTTPException: Raises a 500 error for any other client errors encountered during the request.
    """
    s3_client = boto3.client("s3")

    # Validate bucket name
    if not validate_bucket_name(bucket_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid bucket name. Must be 3-63 characters, lowercase, alphanumeric or hyphens.",
        )

    try:
        # Use a delimiter to list only the top-level "folders"
        response = s3_client.list_objects_v2(Bucket=bucket_name, Delimiter="/")

        if "CommonPrefixes" not in response:
            return {"message": "No folders found in the bucket", "folders": []}

        # Extract each "folder" name from the CommonPrefixes key
        folders = [prefix["Prefix"] for prefix in response["CommonPrefixes"]]

        return {
            "message": "Folders retrieved successfully",
            "bucket_name": bucket_name,
            "folders": folders,
        }

    except s3_client.exceptions.NoSuchBucket:
        raise HTTPException(
            status_code=404, detail=f"Bucket {bucket_name} does not exist"
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDenied":
            raise HTTPException(
                status_code=403, detail=f"Access denied for bucket {bucket_name}"
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/buckets/{bucket_name}/folders/{folder_name}/images-urls", status_code=200)
async def get_public_image_urls_in_folder(
    bucket_name: str, folder_name: str, current_user: dict = Depends(get_current_user)
):
    """
    Get public URLs for images in a specific folder within an S3 bucket.

    Args:
        bucket_name: Name of the S3 bucket.
        folder_name: Path to the folder within the bucket (e.g., 'images/').

    Returns:
        dict: List of public image URLs within the specified folder.
    """
    s3_client = boto3.client("s3")

    # Validate bucket name
    if not validate_bucket_name(bucket_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid bucket name. Must be 3-63 characters, lowercase, alphanumeric or hyphens.",
        )

    # Ensure folder name ends with a trailing slash
    if not folder_name.endswith("/"):
        folder_name += "/"

    try:
        # Determine the correct region for the bucket
        bucket_location = s3_client.get_bucket_location(Bucket=bucket_name)
        region = bucket_location["LocationConstraint"]
        print(f"Region: {region}")

        # Handle the us-east-1 special case, as LocationConstraint returns None for it
        if region is None:
            region = "us-east-1"

        print(f"determined region is Region: {region}")

        # Reinitialize the S3 client with the correct region to avoid cross-region issues
        s3_client = boto3.client("s3", region_name=region)

        # List objects in the specified folder
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=folder_name)

        if "Contents" not in response:
            return {"message": "Folder is empty or does not exist", "image_urls": []}

        image_urls = []
        for obj in response["Contents"]:
            key = obj["Key"]
            # Filter for common image formats
            if key.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
                # Construct the public URL for each image using the correct region
                url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"
                image_urls.append({"key": key, "url": url})

        return {
            "message": "Image URLs retrieved successfully",
            "bucket_name": bucket_name,
            "folder_name": folder_name,
            "image_urls": image_urls,
        }

    except s3_client.exceptions.NoSuchBucket:
        raise HTTPException(
            status_code=404, detail=f"Bucket {bucket_name} does not exist"
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDenied":
            raise HTTPException(
                status_code=403, detail=f"Access denied for bucket {bucket_name}"
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))
