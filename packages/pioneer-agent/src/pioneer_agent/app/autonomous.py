"""Entry point for the autonomous observe → plan → act loop.

Usage:
  PYTHONPATH=src python3 -m pioneer_agent.app.autonomous
  PYTHONPATH=src python3 -m pioneer_agent.app.autonomous --max-iterations 5
"""
from __future__ import annotations

import argparse
import logging

from pioneer_agent.adapters.bridge_client import BridgeClient
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.perception.ui_registry import UIRegistry
from pioneer_agent.perception.vision import VisionClient
from pioneer_agent.perception.vision_sync import VisionSync
from pioneer_agent.runtime.autonomous_loop import AutonomousLoop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the autonomous pioneer-agent loop.")
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="Stop after N ticks (default: run forever).")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    with BridgeClient() as bridge:
        vision = VisionClient()
        registry = UIRegistry.load()
        ui = UIActions(bridge, registry, vision=vision)
        loop = AutonomousLoop(
            bridge=bridge,
            vision_sync=VisionSync(vision),
            ui_actions=ui,
        )
        loop.run_forever(max_iterations=args.max_iterations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
