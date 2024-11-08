# S3 Bucket API - AWS Lambda Deployment

## Prerequisites
- AWS CLI installed and configured
- AWS SAM CLI installed
- Python 3.8+
- AWS Account

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure AWS Credentials:
```bash
aws configure
```

## Deployment

### Local Testing
```bash
sam local start-api
```

### Deploy to AWS
```bash
sam build
sam deploy --guided
```

## Environment Variables
Set the following environment variables in AWS Lambda console:
- `AWS_DEFAULT_REGION`: Your preferred AWS region
- `LOG_LEVEL`: Logging verbosity (e.g., INFO, DEBUG)

## Monitoring
- Check CloudWatch Logs
- Monitor Lambda function metrics
- Use AWS X-Ray for tracing performance
