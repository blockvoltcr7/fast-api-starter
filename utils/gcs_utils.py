from google.cloud import storage
from typing import Optional, List

class GCSClient:
    """Utility class for Google Cloud Storage operations"""

    def __init__(self, project_id: str):
        """Initialize GCS client
        
        Args:
            project_id: Google Cloud project ID
        """
        self.client = storage.Client(project=project_id)

    def create_bucket(self, bucket_name: str, location: str = "US") -> Optional[storage.Bucket]:
        """Create a new GCS bucket
        
        Args:
            bucket_name: Name of the bucket to create
            location: Location for the bucket (default: "US")
            
        Returns:
            Bucket object if successful, None if failed
        """
        try:
            bucket = self.client.bucket(bucket_name)
            bucket.location = location
            bucket.create()
            return bucket
        except Exception as e:
            print(f"Error creating bucket: {e}")
            return None

    def get_bucket(self, bucket_name: str) -> Optional[storage.Bucket]:
        """Get a GCS bucket by name
        
        Args:
            bucket_name: Name of the bucket to retrieve
            
        Returns:
            Bucket object if exists, None if not found
        """
        try:
            bucket = self.client.get_bucket(bucket_name)
            return bucket
        except Exception as e:
            print(f"Error getting bucket: {e}")
            return None

    def list_buckets(self) -> List[storage.Bucket]:
        """List all buckets in the project
        
        Returns:
            List of bucket objects
        """
        return list(self.client.list_buckets())
