from utils.gcs_utils import GCSClient

def test_create_bucket():
    gcs_client = GCSClient(project_id="my-project")
    bucket = gcs_client.create_bucket(bucket_name="my-test-bucket")
    assert bucket is not None
    assert bucket.name == "my-test-bucket"
