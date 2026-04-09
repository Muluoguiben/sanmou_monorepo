from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.mcp_server.tooling import KnowledgeToolHandler
from qa_agent.service.query_service import QueryService


SERVER_INFO = {"name": "sanguo-kb", "version": "0.1.0"}


class StdioJsonRpcServer:
    def __init__(self, handler: KnowledgeToolHandler) -> None:
        self.handler = handler

    def serve_forever(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                break
            if "id" not in message and message.get("method") == "notifications/initialized":
                continue
            response = self._handle_message(message)
            if response is not None:
                self._write_message(response)

    def _handle_message(self, message: dict) -> dict | None:
        method = message.get("method")
        request_id = message.get("id")
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": SERVER_INFO,
                        "capabilities": {"tools": {}},
                    },
                }
            if method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": self.handler.tool_definitions()},
                }
            if method == "tools/call":
                params = message.get("params", {})
                result = self.handler.call_tool(params["name"], params.get("arguments", {}))
                return {"jsonrpc": "2.0", "id": request_id, "result": result}
            if request_id is None:
                return None
            return self._error_response(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            if request_id is None:
                return None
            return self._error_response(request_id, -32000, str(exc))

    @staticmethod
    def _error_response(request_id: object, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _read_message() -> dict | None:
        headers: dict[str, str] = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            decoded = line.decode("utf-8").strip()
            if not decoded:
                break
            name, _, value = decoded.partition(":")
            headers[name.lower()] = value.strip()
        content_length = int(headers.get("content-length", "0"))
        if content_length <= 0:
            return None
        body = sys.stdin.buffer.read(content_length)
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    @staticmethod
    def _write_message(payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Sanguo KB MCP stdio server.")
    parser.add_argument(
        "--sources-dir",
        default="knowledge_sources",
        help="Directory that stores YAML knowledge sources.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    source_paths = discover_source_paths(project_root / args.sources_dir)
    service = QueryService.from_source_paths(source_paths)
    handler = KnowledgeToolHandler(service)
    StdioJsonRpcServer(handler).serve_forever()


if __name__ == "__main__":
    main()
