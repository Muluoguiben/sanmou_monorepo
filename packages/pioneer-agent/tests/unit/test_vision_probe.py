from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from PIL import Image

from pioneer_agent.app.vision_probe import main


@dataclass
class _Result:
    data: dict[str, Any]
    model: str = "fixture-model"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _Client:
    _model = "fixture-model"

    def __init__(self) -> None:
        self.payloads = [
            {
                "page_type": "main_map",
                "resources": {},
                "visible_notes": [],
            },
            {
                "page_type": "main_map",
                "filter_panel_visible": False,
                "resource_filter_enabled": False,
                "selected_resource_types": [],
                "selected_levels": [],
                "filter_button_visible": False,
                "filter_button_enabled": False,
                "apply_button_visible": False,
                "apply_button_enabled": False,
                "resource_toggles": [],
                "level_toggles": [],
                "lands": [],
                "visible_notes": [],
            },
        ]

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _Result(data=self.payloads.pop(0))


class VisionProbeTests(unittest.TestCase):
    def test_full_sync_reports_provider_hash_domains_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "shot.png"
            Image.new("RGB", (8, 6), (0, 0, 0)).save(image_path)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch(
                    "pioneer_agent.app.vision_probe.build_vision_client",
                    return_value=_Client(),
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                exit_code = main(
                    ["--image", str(image_path), "--mode", "full_sync"]
                )

        self.assertEqual(exit_code, 0)
        state = json.loads(stdout.getvalue())
        self.assertEqual(state["global_state"]["page_type"], "main_map")
        self.assertEqual(state["map_state"]["candidate_land_count"], 0)
        diagnostics = stderr.getvalue()
        self.assertIn("image sha256:", diagnostics)
        self.assertIn("provider: _Client model=fixture-model", diagnostics)
        self.assertIn("domains: ['resource_bar', 'map_land']", diagnostics)


if __name__ == "__main__":
    unittest.main()
