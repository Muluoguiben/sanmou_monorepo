"""R24: real filesystem regressions; API dependencies are mandatory here."""
from io import BytesIO
import base64
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from pioneer_agent.app.advisor_api import AdvisorApiService, MAX_UPLOAD_BYTES, create_app


class AdvisorUploadCleanupTests(unittest.TestCase):
    def test_corrupt_png_checksum_returns_400_and_removes_upload(self):
        corrupted = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII="
        )
        with TemporaryDirectory() as tmp:
            service = AdvisorApiService(data_dir=Path(tmp), default_mock_mode=True)
            with TestClient(create_app(service)) as client:
                response = client.post("/api/advisor/analyze", files={
                    "screenshot": ("bad-checksum.png", corrupted, "image/png")
                })
            self.assertEqual(response.status_code, 400, response.text)
            self.assertEqual(list(service.upload_dir.iterdir()), [])

    def test_oversized_http_upload_returns_413_and_leaves_no_file(self):
        with TemporaryDirectory() as tmp:
            service = AdvisorApiService(data_dir=Path(tmp), default_mock_mode=True)
            with TestClient(create_app(service)) as client:
                response = client.post("/api/advisor/analyze", files={
                    "screenshot": ("too-large.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")
                })
            self.assertEqual(response.status_code, 413, response.text)
            self.assertEqual(list(service.upload_dir.iterdir()), [])
            self.assertFalse(service.report_log.exists())

    def test_interrupted_read_closes_writer_and_removes_partial_file(self):
        class BrokenUpload:
            calls = 0
            def read(self, size):
                self.calls += 1
                if self.calls == 1:
                    return b"partial"
                raise OSError("synthetic read interruption")

        with TemporaryDirectory() as tmp:
            service = AdvisorApiService(data_dir=Path(tmp))
            with self.assertRaisesRegex(OSError, "synthetic read interruption"):
                service._save_upload(UploadFile(file=BrokenUpload(), filename="broken.png"))
            self.assertEqual(list(service.upload_dir.iterdir()), [])

    def test_exact_limit_is_validated_as_image_not_rejected_as_oversized(self):
        with TemporaryDirectory() as tmp:
            service = AdvisorApiService(data_dir=Path(tmp))
            with self.assertRaises(HTTPException) as raised:
                service._save_upload(UploadFile(file=BytesIO(b"x" * MAX_UPLOAD_BYTES), filename="invalid.png"))
            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(list(service.upload_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
