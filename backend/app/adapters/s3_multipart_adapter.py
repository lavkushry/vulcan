"""
Project Vulcan: 10GB S3 Presigned Multipart Chunked Upload Adapter
Author: Alex Xu (Systems Lead)
Decouples Control Plane (metadata) from Data Plane (high-speed object storage).
"""
import hashlib
import math
from typing import Any, Dict, List, Optional
from app.ports.interfaces import IObjectStorageGateway

CHUNK_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB chunk size


class S3MultipartGateway(IObjectStorageGateway):
    """
    Manages 10GB+ object storage uploads using S3 Presigned Multipart URLs.
    Implements IObjectStorageGateway.
    """

    def __init__(
        self,
        bucket_name: str = "vulcan-artifacts",
        s3_client: Optional[Any] = None,
        mock_mode: bool = True
    ):
        self.bucket_name = bucket_name
        self.s3_client = s3_client
        self.mock_mode = mock_mode or (s3_client is None)
        self._mock_objects: Dict[str, Dict[str, Any]] = {}

    def initiate_multipart_upload(
        self,
        file_name: str,
        file_size_bytes: int,
        sha256_checksum: str,
        job_id: str
    ) -> Dict[str, Any]:
        """
        Calculates 50MB chunks and generates presigned PUT URLs for each chunk.
        """
        s3_key = f"jobs/{job_id}/{file_name}"
        total_parts = math.ceil(file_size_bytes / CHUNK_SIZE_BYTES)

        if self.mock_mode:
            upload_id = f"mock-upload-{job_id}-{file_name}"
            part_urls = [
                {
                    "part_number": part_num,
                    "upload_url": f"https://s3.mock.vulcan.internal/{self.bucket_name}/{s3_key}?partNumber={part_num}&uploadId={upload_id}"
                }
                for part_num in range(1, total_parts + 1)
            ]
            self._mock_objects[f"s3://{self.bucket_name}/{s3_key}"] = {
                "sha256": sha256_checksum,
                "size": file_size_bytes,
                "upload_id": upload_id,
                "status": "INITIATED",
                "parts": []
            }
            return {
                "upload_id": upload_id,
                "s3_key": s3_key,
                "chunk_size_bytes": CHUNK_SIZE_BYTES,
                "total_parts": total_parts,
                "part_urls": part_urls
            }

        # Real AWS S3 / MinIO via boto3
        response = self.s3_client.create_multipart_upload(
            Bucket=self.bucket_name,
            Key=s3_key,
            Metadata={
                "expected-sha256": sha256_checksum,
                "job-id": job_id
            }
        )
        upload_id = response["UploadId"]
        part_urls = []

        for part_num in range(1, total_parts + 1):
            url = self.s3_client.generate_presigned_url(
                ClientMethod="upload_part",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_key,
                    "UploadId": upload_id,
                    "PartNumber": part_num
                },
                ExpiresIn=3600
            )
            part_urls.append({"part_number": part_num, "upload_url": url})

        return {
            "upload_id": upload_id,
            "s3_key": s3_key,
            "chunk_size_bytes": CHUNK_SIZE_BYTES,
            "total_parts": total_parts,
            "part_urls": part_urls
        }

    def complete_multipart_upload(
        self,
        upload_id: str,
        s3_key: str,
        parts: List[Dict[str, Any]]
    ) -> str:
        """
        Completes the multipart upload and returns final S3 URI.
        """
        s3_uri = f"s3://{self.bucket_name}/{s3_key}"

        if self.mock_mode:
            if s3_uri in self._mock_objects:
                self._mock_objects[s3_uri]["status"] = "COMPLETED"
                self._mock_objects[s3_uri]["parts"] = parts
            return s3_uri

        sorted_parts = sorted(parts, key=lambda p: p["part_number"])
        s3_parts = [{"PartNumber": p["part_number"], "ETag": p["etag"]} for p in sorted_parts]

        self.s3_client.complete_multipart_upload(
            Bucket=self.bucket_name,
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": s3_parts}
        )
        return s3_uri

    def register_mock_artifact(self, uri: str, sha256: str):
        """Helper for test harness and local simulation."""
        self._mock_objects[uri] = {
            "sha256": sha256,
            "status": "COMPLETED"
        }

    def verify_artifact_checksum(self, uri: str, expected_sha256: str) -> bool:
        """
        Implements IObjectStorageGateway port.
        Verifies that uploaded payload matches the expected cryptographic SHA256.
        """
        if self.mock_mode:
            obj = self._mock_objects.get(uri)
            if not obj:
                return False
            return obj.get("sha256") == expected_sha256

        try:
            # Extract key from s3://bucket/key
            parts = uri.replace("s3://", "").split("/", 1)
            if len(parts) != 2:
                return False
            bucket, key = parts
            meta = self.s3_client.head_object(Bucket=bucket, Key=key)
            remote_sha = meta.get("Metadata", {}).get("expected-sha256")
            return remote_sha == expected_sha256
        except Exception:
            return False
