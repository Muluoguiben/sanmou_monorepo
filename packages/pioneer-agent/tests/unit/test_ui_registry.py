"""Tests for the fixed-position UI button registry."""
from __future__ import annotations

import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pioneer_agent.perception.ui_registry import UIButton, UIRegistry


class UIRegistryTests(unittest.TestCase):
    def _write_layout(self, dir_path: Path, body: str) -> Path:
        path = dir_path / "ui_layout.yaml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_default_layout_loads(self) -> None:
        registry = UIRegistry.load()
        # Must include every bottom-menu key we depend on
        for key in ["chu_cheng", "wu_jiang", "tong_meng", "zhi_ye", "zheng_zhan_jun_yan", "esc_close"]:
            self.assertIn(key, registry.keys())
        b = registry.get("wu_jiang")
        self.assertEqual(b.label, "武将")
        self.assertTrue(0 < b.x_frac < 1)
        self.assertTrue(0 < b.y_frac < 1)

    def test_resolve_pixel_scales_to_window(self) -> None:
        with TemporaryDirectory() as tmp:
            path = self._write_layout(
                Path(tmp),
                textwrap.dedent(
                    """
                    layout_version: 1
                    buttons:
                      foo:
                        label: "测试"
                        x: 0.5
                        y: 0.25
                    """
                ),
            )
            reg = UIRegistry.load(path)
            self.assertEqual(reg.resolve_pixel("foo", 1920, 1080), (960, 270))
            self.assertEqual(reg.resolve_pixel("foo", 2559, 1329), (1280, 332))

    def test_missing_key_raises(self) -> None:
        reg = UIRegistry({"only": UIButton("only", "one", 0.5, 0.5)})
        with self.assertRaises(KeyError):
            reg.get("nope")

    def test_empty_config_is_tolerated(self) -> None:
        with TemporaryDirectory() as tmp:
            path = self._write_layout(
                Path(tmp), "layout_version: 1\nbuttons: {}\n"
            )
            reg = UIRegistry.load(path)
            self.assertEqual(reg.keys(), [])


if __name__ == "__main__":
    unittest.main()
