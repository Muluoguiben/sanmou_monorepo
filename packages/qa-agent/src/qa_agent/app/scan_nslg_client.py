from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_package import scan_client_package, write_client_package_manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan a local NSLG client install into an offline evidence manifest for qa-agent ingestion planning."
    )
    parser.add_argument("--root", required=True, help="NSLG client install root, e.g. the 'NSLG Game' directory.")
    parser.add_argument("--output", help="YAML output path. If omitted, JSON is printed to stdout.")
    parser.add_argument(
        "--include-absolute-paths",
        action="store_true",
        help="Include the machine-local root path in the manifest. Disabled by default for portability.",
    )
    parser.add_argument(
        "--include-runtime-files",
        action="store_true",
        help="Include LocalPersistentData, logs, .db, and .log files. Disabled by default to avoid account/runtime data.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    manifest = scan_client_package(
        Path(args.root),
        include_absolute_paths=args.include_absolute_paths,
        include_runtime_files=args.include_runtime_files,
    )
    if args.output:
        write_client_package_manifest(manifest, Path(args.output))
        print(
            json.dumps(
                {
                    "output": args.output,
                    "included_files": manifest.included_files,
                    "skipped_files": manifest.skipped_files,
                    "version_info": manifest.version_info,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
