import asyncio
import io

from minio import Minio
from minio.error import S3Error

HTML_CONTENT_TYPE = "text/html; charset=utf-8"


class BucketMissing(RuntimeError):
    """The raw-HTML bucket is not there; the stack's `minio-init` service should have created it."""


def html_key(document_id: str) -> str:
    return f"html/{document_id}.html"


class Storage:
    """Raw HTML in MinIO. The minio client is blocking, so every call runs in a worker thread."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, *, bucket: str = "iw-raw", secure: bool = False):
        self.endpoint, self.access_key, self.secret_key, self.bucket = endpoint, access_key, secret_key, bucket
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    async def check_bucket(self) -> None:
        """Fail clearly if the bucket is missing. It is created by `minio-init` (module C), never here: the
        app user is limited to this bucket and may not be allowed to create one."""
        exists = await asyncio.to_thread(self._client.bucket_exists, self.bucket)
        if not exists:
            raise BucketMissing(f"object storage bucket {self.bucket!r} does not exist (created by minio-init)")

    async def put_html(self, document_id: str, html: str) -> str:
        data = html.encode("utf-8")
        key = html_key(document_id)
        await asyncio.to_thread(
            self._client.put_object, self.bucket, key, io.BytesIO(data), len(data), content_type=HTML_CONTENT_TYPE
        )
        return key

    async def remove(self, key: str) -> None:
        await asyncio.to_thread(self._client.remove_object, self.bucket, key)

    async def exists(self, key: str) -> bool:
        def stat() -> bool:
            try:
                self._client.stat_object(self.bucket, key)
            except S3Error as exc:
                if exc.code in {"NoSuchKey", "NoSuchObject"}:
                    return False
                raise
            return True

        return await asyncio.to_thread(stat)

    async def list_keys(self) -> list[str]:
        return await asyncio.to_thread(
            lambda: [obj.object_name for obj in self._client.list_objects(self.bucket, recursive=True)]
        )
