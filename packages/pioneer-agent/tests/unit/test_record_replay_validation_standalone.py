from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


VALIDATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "pioneer_agent"
    / "record_replay"
    / "validation.py"
)


def _load_validation_module():
    spec = importlib.util.spec_from_file_location(
        "sanmou_record_replay_validation_standalone_test",
        VALIDATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load standalone Record & Replay validation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StandaloneRecordReplayValidationTests(unittest.TestCase):
    def test_repeated_fresh_file_reads_do_not_false_positive(self) -> None:
        validation = _load_validation_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(100):
                path = root / f"fresh-{index:03d}.json"
                payload = f'{{"index":{index}}}'.encode("ascii")
                path.write_bytes(payload)

                loaded = validation.read_bounded_regular_file(
                    path,
                    max_bytes=1_024,
                    label="fresh probe",
                )
                self.assertEqual(loaded.payload, payload)
                reopened = validation.read_bounded_regular_file(
                    path,
                    max_bytes=1_024,
                    label="fresh reopen probe",
                )
                self.assertEqual(reopened.identity, loaded.identity)

    def test_same_inode_rewrite_during_read_remains_rejected(self) -> None:
        validation = _load_validation_module()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            original_payload = b'{"value":"original"}\n'
            replacement = b'{"value":"tampered"}\n'
            self.assertEqual(len(original_payload), len(replacement))
            path.write_bytes(original_payload)
            original_stat = path.stat()
            original_read = validation.os.read
            mutated = False

            def mutate_after_first_read(descriptor: int, size: int) -> bytes:
                nonlocal mutated
                chunk = original_read(descriptor, size)
                if not mutated:
                    mutated = True
                    path.write_bytes(replacement)
                    os.utime(
                        path,
                        ns=(
                            original_stat.st_atime_ns,
                            original_stat.st_mtime_ns + 1_000_000_000,
                        ),
                    )
                return chunk

            with patch.object(
                validation.os,
                "read",
                side_effect=mutate_after_first_read,
            ):
                with self.assertRaisesRegex(ValueError, "changed while it was read"):
                    validation.read_bounded_regular_file(
                        path,
                        max_bytes=1_024,
                        label="rewrite probe",
                    )


if __name__ == "__main__":
    unittest.main()
