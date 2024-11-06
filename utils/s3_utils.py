import boto3
from botocore.exceptions import ClientError
from typing import Optional, BinaryIO, Dict, Any

class S3Client:
    """Utility class for AWS S3 operations"""
    
    def __init__(self, bucket_name: str):
        """
        Initialize S3 client
        
        Args:
            bucket_name (str): Name of the S3 bucket
        """
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name

    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """
        Upload a file to S3 bucket
        
        Args:
            file_path (str): Local path to the file
            s3_key (str): Destination path in S3
            
        Returns:
            bool: True if upload successful, False otherwise
        """
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            return True
        except ClientError as e:
            print(f"Error uploading file: {e}")
            return False

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """
        Download a file from S3 bucket
        
        Args:
            s3_key (str): Path of file in S3
            local_path (str): Local destination path
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            return True
        except ClientError as e:
            print(f"Error downloading file: {e}")
            return False

    def read_file(self, s3_key: str) -> Optional[bytes]:
        """
        Read file content from S3
        
        Args:
            s3_key (str): Path of file in S3
            
        Returns:
            Optional[bytes]: File content if successful, None otherwise
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read()
        except ClientError as e:
            print(f"Error reading file: {e}")
            return None

    def write_file(self, s3_key: str, content: BinaryIO) -> bool:
        """
        Write content to a file in S3
        
        Args:
            s3_key (str): Destination path in S3
            content (BinaryIO): Content to write
            
        Returns:
            bool: True if write successful, False otherwise
        """
        try:
            self.s3_client.upload_fileobj(content, self.bucket_name, s3_key)
            return True
        except ClientError as e:
            print(f"Error writing file: {e}")
            return False

    def list_files(self, prefix: str = "") -> list[Dict[str, Any]]:
        """
        List files in S3 bucket
        
        Args:
            prefix (str): Filter results by prefix
            
        Returns:
            list[Dict[str, Any]]: List of file information
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            return response.get('Contents', [])
        except ClientError as e:
            print(f"Error listing files: {e}")
            return []
