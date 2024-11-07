# JWT Authentication in S3 Bucket API

## Overview
This document provides a comprehensive guide to using JWT (JSON Web Token) authentication in the S3 Bucket API.

## Authentication Workflow

### 1. Obtain an Access Token
To access the S3 Bucket API endpoints, you must first obtain a JWT access token by authenticating with valid credentials.

#### Endpoint
- **URL**: `/token`
- **Method**: `POST`
- **Content-Type**: `application/x-www-form-urlencoded`

#### Request Parameters
- `username`: Your username
- `password`: Your password

#### Example Curl Command
```bash
curl -X POST "http://localhost:8000/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=testpassword"
```

#### Successful Response
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

### 2. Use the Access Token
Include the access token in the `Authorization` header for all subsequent API requests.

#### Header Format
```
Authorization: Bearer <access_token>
```

## API Endpoint Examples with JWT Authentication

### List Buckets
```bash
# Get access token first
TOKEN=$(curl -X POST "http://localhost:8000/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=testpassword" | jq -r .access_token)

# List buckets using the token
curl -X GET "http://localhost:8000/buckets/" \
     -H "Authorization: Bearer $TOKEN"
```

### Create Bucket
```bash
# Create bucket with auto-generated name
curl -X POST "http://localhost:8000/buckets/create" \
     -H "Authorization: Bearer $TOKEN"

# Create bucket with custom name and region
curl -X POST "http://localhost:8000/buckets/create?bucket_name=my-custom-bucket&region=us-west-2" \
     -H "Authorization: Bearer $TOKEN"
```

### Get Bucket Details
```bash
# Get details of a specific bucket
curl -X GET "http://localhost:8000/buckets/my-bucket-name" \
     -H "Authorization: Bearer $TOKEN"
```

## Token Characteristics

### Token Expiration
- Default expiration: 30 minutes
- After expiration, you must request a new token

### Security Considerations
- Keep your access token confidential
- Do not share tokens between users
- Tokens are tied to the authenticated user

## Troubleshooting

### Common Authentication Errors
- **401 Unauthorized**: Invalid or expired token
- **400 Bad Request**: Incorrect username or password

### Regenerating Tokens
Simply request a new token using the `/token` endpoint with valid credentials.

## Development and Testing

### Test User Credentials
For development and testing, use these default credentials:
- **Username**: `testuser`
- **Password**: `testpassword`

### Replacing Test Users
In a production environment, replace the mock user database in `auth/jwt_auth.py` with a real user authentication system.

## Best Practices
- Use HTTPS in production to encrypt token transmission
- Implement token refresh mechanism
- Implement proper user management
- Rotate secret keys periodically

## Configuration

### JWT Configuration
Located in `auth/jwt_auth.py`:
- `SECRET_KEY`: Used for token signing (MUST be changed in production)
- `ALGORITHM`: JWT signing algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token validity duration

### Recommended Production Setup
- Use environment variables for `SECRET_KEY`
- Implement secure key rotation
- Use a robust user authentication backend
```
