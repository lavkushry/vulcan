"""
Project Vulcan: 10GB S3 Presigned Multipart Chunking Tests
Author: Alex Xu (Distributed Systems Lead)
Verifies:
1. 10GB (10,737,418,240 byte) partition produces exactly 205 parts at 50MB each.
2. Presigned URLs are generated per part.
3. Multi-part upload assembly and final URI return.
4. SHA256 checksum verification gate.
"""
import unittest
from app.adapters.s3_multipart_adapter import S3MultipartGateway, CHUNK_SIZE_BYTES


class TestS3MultipartUpload(unittest.TestCase):

    def setUp(self):
        self.gateway = S3MultipartGateway(bucket_name="pnc-vulcan-artifacts-test", mock_mode=True)

    def test_ten_gigabyte_partitioning_into_205_parts(self):
        """10 GB payload partitioned into 50MB parts yields ceil(10737418240 / 52428800) = 205 parts."""
        ten_gb_bytes = 10 * 1024 * 1024 * 1024
        expected_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        resp = self.gateway.initiate_multipart_upload(
            file_name="rhel-9-hardened.iso",
            file_size_bytes=ten_gb_bytes,
            sha256_checksum=expected_sha,
            job_id="EXEC-8821"
        )

        self.assertEqual(resp["total_parts"], 205)
        self.assertEqual(resp["chunk_size_bytes"], CHUNK_SIZE_BYTES)
        self.assertEqual(len(resp["part_urls"]), 205)
        self.assertEqual(resp["part_urls"][0]["part_number"], 1)
        self.assertEqual(resp["part_urls"][-1]["part_number"], 205)

    def test_complete_multipart_and_checksum_verification(self):
        """Complete upload and verify cryptographic checksum matching."""
        ten_gb_bytes = 10 * 1024 * 1024 * 1024
        expected_sha = "valid_sha256_hash_1234567890abcdef"

        resp = self.gateway.initiate_multipart_upload(
            file_name="rhel-9-hardened.iso",
            file_size_bytes=ten_gb_bytes,
            sha256_checksum=expected_sha,
            job_id="EXEC-8822"
        )

        mock_parts = [{"part_number": 1, "etag": "etag-chunk-1"}]
        final_uri = self.gateway.complete_multipart_upload(
            upload_id=resp["upload_id"],
            s3_key=resp["s3_key"],
            parts=mock_parts
        )

        self.assertEqual(final_uri, "s3://pnc-vulcan-artifacts-test/jobs/EXEC-8822/rhel-9-hardened.iso")
        self.assertTrue(self.gateway.verify_artifact_checksum(final_uri, expected_sha))
        self.assertFalse(self.gateway.verify_artifact_checksum(final_uri, "tampered_wrong_sha256"))

    def test_abort_multipart_upload(self):
        """BKND-14: Aborting multipart upload cancels and purges in-flight state."""
        resp = self.gateway.initiate_multipart_upload(
            file_name="corrupted-binary.bin",
            file_size_bytes=100 * 1024 * 1024,
            sha256_checksum="dummy-sha",
            job_id="EXEC-ABORT"
        )
        s3_uri = f"s3://pnc-vulcan-artifacts-test/{resp['s3_key']}"
        self.assertEqual(self.gateway._mock_objects[s3_uri]["status"], "INITIATED")

        aborted = self.gateway.abort_multipart_upload(resp["upload_id"], resp["s3_key"])
        self.assertTrue(aborted)
        self.assertEqual(self.gateway._mock_objects[s3_uri]["status"], "ABORTED")

    def test_cleanup_orphaned_uploads(self):
        """BKND-14: Automatic sweep of abandoned uploads older than max_age_seconds."""
        from datetime import datetime, timezone, timedelta

        # 1. Old upload (48 hours ago)
        resp1 = self.gateway.initiate_multipart_upload(
            file_name="old.iso",
            file_size_bytes=50 * 1024 * 1024,
            sha256_checksum="sha-1",
            job_id="EXEC-OLD"
        )
        uri1 = f"s3://pnc-vulcan-artifacts-test/{resp1['s3_key']}"
        self.gateway._mock_objects[uri1]["initiated_at"] = datetime.now(timezone.utc) - timedelta(hours=48)

        # 2. Fresh upload (10 minutes ago)
        resp2 = self.gateway.initiate_multipart_upload(
            file_name="fresh.iso",
            file_size_bytes=50 * 1024 * 1024,
            sha256_checksum="sha-2",
            job_id="EXEC-FRESH"
        )

        cleaned = self.gateway.cleanup_orphaned_uploads(max_age_seconds=86400)
        self.assertEqual(cleaned, 1)
        self.assertEqual(self.gateway._mock_objects[uri1]["status"], "ABORTED")
        uri2 = f"s3://pnc-vulcan-artifacts-test/{resp2['s3_key']}"
        self.assertEqual(self.gateway._mock_objects[uri2]["status"], "INITIATED")

    def test_rewrite_presigned_url_for_browser_clients(self):
        """Presigned URLs sign against internal host but rewrite to public host for browsers."""
        from app.adapters.s3_multipart_adapter import rewrite_presigned_url

        internal_url = "http://minio:9000/vulcan-artifacts/jobs/EXEC-1/file.iso?partNumber=1&uploadId=xyz"
        rewritten = rewrite_presigned_url(
            internal_url,
            internal_endpoint="http://minio:9000",
            public_endpoint="http://141.148.195.233:9000"
        )
        self.assertEqual(
            rewritten,
            "http://141.148.195.233:9000/vulcan-artifacts/jobs/EXEC-1/file.iso?partNumber=1&uploadId=xyz"
        )

    def test_boto3_real_client_integration(self):
        """Test S3MultipartGateway using a mocked boto3 client to verify exact SDK contracts."""
        from unittest.mock import MagicMock
        from datetime import datetime, timezone

        mock_boto = MagicMock()
        mock_boto.create_multipart_upload.return_value = {"UploadId": "real-upload-99"}
        mock_boto.generate_presigned_url.return_value = "http://minio:9000/vulcan-artifacts/key?uploadId=real-upload-99"
        mock_boto.head_object.return_value = {
            "Metadata": {"expected-sha256": "real-sha256-verified"}
        }

        gateway = S3MultipartGateway(
            bucket_name="test-bucket",
            endpoint_url="http://minio:9000",
            public_endpoint_url="http://141.148.195.233:9000",
            s3_client=mock_boto
        )

        resp = gateway.initiate_multipart_upload(
            file_name="artifact.tar.gz",
            file_size_bytes=100 * 1024 * 1024,
            sha256_checksum="real-sha256-verified",
            job_id="JOB-BOTO"
        )

        self.assertEqual(resp["upload_id"], "real-upload-99")
        self.assertEqual(len(resp["part_urls"]), 2)
        # Verify URL was rewritten to public endpoint
        self.assertTrue(resp["part_urls"][0]["upload_url"].startswith("http://141.148.195.233:9000"))

        # Complete
        gateway.complete_multipart_upload("real-upload-99", "jobs/JOB-BOTO/artifact.tar.gz", [{"part_number": 1, "etag": "e1"}])
        mock_boto.complete_multipart_upload.assert_called_once()

        # Checksum
        self.assertTrue(gateway.verify_artifact_checksum("s3://test-bucket/jobs/JOB-BOTO/artifact.tar.gz", "real-sha256-verified"))

        # Abort
        gateway.abort_multipart_upload("real-upload-99", "jobs/JOB-BOTO/artifact.tar.gz")
        mock_boto.abort_multipart_upload.assert_called_once_with(
            Bucket="test-bucket",
            Key="jobs/JOB-BOTO/artifact.tar.gz",
            UploadId="real-upload-99"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
