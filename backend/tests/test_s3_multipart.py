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


if __name__ == "__main__":
    unittest.main(verbosity=2)
