from utils.gcs_utils import GCSClient


def test_create_bucket():
    gcs_client = GCSClient(project_id="rflkt-441001")
    bucket = gcs_client.create_bucket(bucket_name="my-test-bucket-897629423")
    print("Bucket creation attempted for: my-test-bucket")
    assert bucket is not None
    assert bucket.name == "my-test-bucket-897629423"
