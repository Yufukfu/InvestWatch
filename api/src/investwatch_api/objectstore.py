"""Object storage behind a small interface (design decision 8): MinIO in the stack, a fake in tests.

The MinIO SDK is synchronous, so calls run in a worker thread. Keys always come from a `documents` row,
never from a request.
"""

from __future__ import annotations

import asyncio
from typing import Protocol


class ObjectStoreError(RuntimeError):
    """The object store is unreachable or answered with an error other than 'not found'."""


class ObjectStore(Protocol):
    async def get(self, key: str) -> bytes | None:
        """Object bytes, or None when the object does not exist."""

    async def ping(self) -> bool:
        """True when the bucket is reachable."""


class MinioStore:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False):
        import urllib3
        from minio import Minio

        # The SDK's default pool retries five times with backoff; behind asyncio.to_thread that keeps worker
        # threads busy long after the 2 s health timeout. Fail fast instead.
        http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=2, read=10),
                                   retries=urllib3.Retry(total=0))
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure, http_client=http)
        self._bucket = bucket

    def _get(self, key: str) -> bytes | None:
        from minio.error import S3Error

        try:
            response = self._client.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code in ("NoSuchKey", "NoSuchObject"):
                return None
            raise ObjectStoreError(exc.code) from None
        except Exception as exc:  # connection errors from urllib3
            raise ObjectStoreError(type(exc).__name__) from None
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def get(self, key: str) -> bytes | None:
        return await asyncio.to_thread(self._get, key)

    async def ping(self) -> bool:
        try:
            return await asyncio.to_thread(self._client.bucket_exists, self._bucket)
        except Exception:
            return False
