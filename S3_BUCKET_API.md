# S3 Bucket API Documentation

## Overview
This API provides endpoints for managing S3 buckets using AWS boto3 client.

## Endpoints

### List Buckets
- **URL**: `/buckets/`
- **Method**: `GET`
- **Description**: Retrieves a list of all S3 buckets
- **Response**:
  - `200 OK`: Returns a list of bucket names
  - `500 Internal Server Error`: If there's an AWS client error

### Create Bucket
- **URL**: `/buckets/create`
- **Method**: `POST`
- **Query Parameters**:
  - `bucket_name` (optional): Custom bucket name
    - Must be 3-63 characters
    - Lowercase alphanumeric or hyphens
  - `region` (optional, default: `us-east-1`): AWS region for bucket creation

- **Responses**:
  - `201 Created`: Bucket successfully created
    ```json
    {
      "message": "Bucket created successfully",
      "bucket_name": "example-bucket",
      "region": "us-east-1"
    }
    ```
  - `400 Bad Request`: Invalid bucket name
  - `409 Conflict`: Bucket already exists
  - `500 Internal Server Error`: Unexpected AWS error

### Create Bucket with Folder
- **URL**: `/buckets/create-with-folder`
- **Method**: `POST`
- **Query Parameters**:
  - `bucket_name` (optional): Custom bucket name
    - Must be 3-63 characters
    - Lowercase alphanumeric or hyphens
  - `region` (optional, default: `us-east-1`): AWS region for bucket creation
  - `folder_name` (optional, default: `new-folder/`): Name of the initial folder to create

- **Responses**:
  - `201 Created`: Bucket and folder successfully created
    ```json
    {
      "message": "Bucket and folder created successfully",
      "bucket_name": "example-bucket",
      "region": "us-east-1",
      "folder_name": "new-folder/"
    }
    ```
  - `400 Bad Request`: Invalid bucket name
  - `409 Conflict`: Bucket already exists
  - `500 Internal Server Error`: Unexpected AWS error

### Get Bucket Details
- **URL**: `/buckets/{bucket_name}`
- **Method**: `GET`
- **Path Parameters**:
  - `bucket_name`: Name of the bucket to retrieve
    - Must be 3-63 characters
    - Lowercase alphanumeric or hyphens

- **Responses**:
  - `200 OK`: Bucket found successfully
    ```json
    {
      "message": "Bucket found successfully",
      "bucket_name": "example-bucket",
      "region": "us-east-1"
    }
    ```
  - `400 Bad Request`: Invalid bucket name
  - `403 Forbidden`: Access denied to the bucket
  - `404 Not Found`: Bucket does not exist
  - `500 Internal Server Error`: Unexpected AWS error

## Example Curl Commands
```bash
# Create bucket with auto-generated name
curl -X POST "http://localhost:8000/buckets/create"

# Get details of a specific bucket
curl -X GET "http://localhost:8000/buckets/my-bucket-name"

# Create bucket with custom name and region
curl -X POST "http://localhost:8000/buckets/create?bucket_name=my-custom-bucket&region=us-west-2"

# Create bucket with a custom folder
curl -X POST "http://localhost:8000/buckets/create-with-folder?bucket_name=my-custom-bucket&folder_name=my-custom-folder/"
```

## Bucket Name Validation Rules
- Length: 3-63 characters
- Lowercase only
- Alphanumeric characters and hyphens
