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


## how to deploy fastapi

### Deploying FastAPI

To deploy your FastAPI application, you can use various methods. Below is an example using the `uvicorn` server and Docker.

#### Using Uvicorn
1. Install Uvicorn:
   ```bash
   pip install uvicorn
   ```

2. Run the FastAPI application:
   ```bash
   uvicorn api.s3_api:app --host 0.0.0.0 --port 8000 --reload
   ```

#### Using Docker
1. Create a `Dockerfile` in your project directory:
   ```dockerfile
   FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

   COPY ./api /app/api
   COPY ./auth /app/auth
   COPY ./streamlit /app/streamlit
   COPY ./requirements.txt /app/

   RUN pip install --no-cache-dir -r /app/requirements.txt

   EXPOSE 8000

   CMD ["uvicorn", "api.s3_api:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. Build the Docker image:
   ```bash
   docker build -t fastapi-s3-app .
   ```

3. Run the Docker container:
   ```bash
   docker run -d --name fastapi-s3-app -p 8000:8000 fastapi-s3-app
   ```

Now your FastAPI application should be running and accessible at `http://localhost:8000`.



## Authentication

The API uses JWT (JSON Web Token) for authentication.

### Obtaining an Access Token
```bash
# Get access token
curl -X POST "http://localhost:8000/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=testpassword"
```

## Example Curl Commands
```bash
# Get access token first
TOKEN=$(curl -X POST "http://localhost:8000/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=testpassword" | jq -r .access_token)

# Create bucket with auto-generated name
curl -X POST "http://localhost:8000/buckets/create" \
     -H "Authorization: Bearer $TOKEN"

# Get details of a specific bucket
curl -X GET "http://localhost:8000/buckets/my-bucket-name" \
     -H "Authorization: Bearer $TOKEN"

# Create bucket with custom name and region
curl -X POST "http://localhost:8000/buckets/create?bucket_name=my-custom-bucket&region=us-west-2" \
     -H "Authorization: Bearer $TOKEN"

# Create bucket with a custom folder
curl -X POST "http://localhost:8000/buckets/create-with-folder?bucket_name=my-custom-bucket&folder_name=my-custom-folder/" \
     -H "Authorization: Bearer $TOKEN"
```

## Bucket Name Validation Rules
- Length: 3-63 characters
- Lowercase only
- Alphanumeric characters and hyphens

## Migrating FastAPI to AWS Lambda

### Prerequisites
- AWS Account
- AWS CLI configured
- Python 3.8+
- Serverless Framework or AWS SAM
- Existing FastAPI application

### Step-by-Step Migration Process

#### 1. Install Required Dependencies
```bash
pip install mangum  # AWS Lambda ASGI adapter
pip install -r requirements.txt
```

#### 2. Create Lambda Handler Wrapper
Create a new file `lambda_handler.py`:
```python
from mangum import Mangum
from api.s3_api import app

handler = Mangum(app)
```

#### 3. Create AWS SAM Template
Create `template.yaml` in project root:
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: S3 Bucket API Lambda

Resources:
  S3BucketAPI:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: lambda_handler.handler
      Runtime: python3.8
      Architectures:
        - x86_64
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY
```

#### 4. Configure AWS Credentials
```bash
aws configure  # Set up AWS credentials
```

#### 5. Deploy Lambda Function
```bash
# Using AWS SAM
sam build
sam deploy --guided
```

#### 6. API Gateway Configuration
- The SAM template automatically creates an API Gateway
- Note the generated endpoint URL
- Use this URL to make API calls

#### 7. IAM Permissions
Ensure Lambda execution role has:
- S3 bucket creation permissions
- S3 list/get bucket permissions

#### 8. Environment Variables
Add AWS region and other configurations via Lambda environment variables

#### Deployment Considerations
- Cold starts may increase initial response time
- Set appropriate Lambda timeout and memory
- Use AWS X-Ray for tracing
- Implement proper error handling
- Consider using Lambda Layers for dependencies

#### Monitoring
- CloudWatch Logs
- CloudWatch Metrics
- AWS X-Ray tracing

#### Cost Optimization
- Use provisioned concurrency for consistent performance
- Adjust memory and timeout settings
- Implement efficient error handling
```
