"""Offline-only development task evaluation. No provider or live switches."""
import argparse
import asyncio
import json
from pathlib import Path

from pioneer_agent.agent_harness.task_eval import evaluate


def main(argv=None):
    root = Path(__file__).resolve().parents[5]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=root)
    parser.add_argument("--suite-root", type=Path, default=root / "packages/pioneer-agent/evaluation/task/development-v1")
    parser.add_argument("--suite", default="suite.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report, code = asyncio.run(evaluate(source_root=args.source_root, suite_root=args.suite_root,
                                            suite_path=args.suite, output=args.output))
    except Exception as exc:
        print(json.dumps({"complete": False, "gate_pass": False, "report_available": False,
                          "infra_error": type(exc).__name__}))
        return 2
    print(json.dumps({"complete": report["complete"], "gate_pass": report["gate_pass"],
                      "totals": report.get("totals"), "output": str(args.output)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
