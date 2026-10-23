"""Authenticated loopback policy gateway; native model inference is injected.

No game API, task loop, prompt persistence, or model-version attestation. The
configured manifest is a deployment binding, checked against each request.
"""
from __future__ import annotations

import argparse
import asyncio
import hmac
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import SecretStr, ValidationError

from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, PolicyTransportResponse, decode_json
from pioneer_agent.adapters.policy_http import PolicyHttpError, SGLangChatBackend, _secret


class PolicyBackend(Protocol):
    async def generate(self, request: PolicyRequest) -> PolicyTransportResponse: ...


def _observe_task(task: asyncio.Task) -> None:
    if not task.cancelled():
        task.exception()


def create_app(*, manifest: PolicyManifest, api_key: SecretStr | str,
               backend: PolicyBackend, timeout_seconds: float = 30.0,
               max_request_bytes: int = 2 * 1024 * 1024,
               max_inflight: int = 16) -> FastAPI:
    pinned = PolicyManifest.model_validate_json(manifest.model_dump_json())
    secret = _secret(api_key, required=True)
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    if type(max_request_bytes) is not int or max_request_bytes < 1:
        raise ValueError("max_request_bytes must be positive")
    if type(max_inflight) is not int or max_inflight < 1:
        raise ValueError("max_inflight must be positive")
    active: set[asyncio.Task] = set()
    counts = {"accepted": 0, "succeeded": 0, "failed": 0, "timeout": 0, "cancelled": 0}

    @asynccontextmanager
    async def lifespan(app):
        yield
        for task in tuple(active):
            task.cancel()
        if active:
            await asyncio.wait(tuple(active), timeout=0.5)
        closer = getattr(backend, "aclose", None)
        if closer is not None:
            await closer()

    app = FastAPI(title="Sanmou policy gateway", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.gateway_counters = counts

    def error(code: str, status: int) -> JSONResponse:
        return JSONResponse({"error": {"code": code}}, status_code=status,
                            headers={"Cache-Control": "no-store"})

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy-gateway"}

    @app.post("/v1/policy/decide")
    async def decide(incoming: Request):
        headers = incoming.headers.getlist("authorization")
        expected = "Bearer " + secret.get_secret_value()
        if len(headers) != 1 or not hmac.compare_digest(headers[0].encode(), expected.encode()):
            return error("unauthorized", 401)
        if incoming.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
            return error("invalid_content_type", 415)
        if len(active) >= max_inflight:
            return error("upstream_busy", 503)
        pending = None
        try:
            async with asyncio.timeout(timeout_seconds):
                body = bytearray()
                async for chunk in incoming.stream():
                    body.extend(chunk)
                    if len(body) > max_request_bytes:
                        return error("request_too_large", 413)
                try:
                    request = PolicyRequest.from_wire(decode_json(bytes(body)))
                except (ValueError, TypeError, ValidationError):
                    return error("invalid_policy_request", 400)
                if request.manifest.sha256 != pinned.sha256:
                    return error("policy_version_mismatch", 409)
                if await incoming.is_disconnected():
                    counts["cancelled"] += 1
                    return error("cancelled", 499)
                # Body reads and disconnect checks yielded control: only this
                # final check plus task insertion form the admission boundary.
                if len(active) >= max_inflight:
                    return error("upstream_busy", 503)
                counts["accepted"] += 1
                pending = asyncio.create_task(backend.generate(request))
                active.add(pending)
                pending.add_done_callback(active.discard)
                pending.add_done_callback(_observe_task)
                while True:
                    done, _ = await asyncio.wait({pending}, timeout=0.02)
                    if await incoming.is_disconnected():
                        counts["cancelled"] += 1
                        return error("cancelled", 499)
                    if done:
                        response = pending.result()
                        response = PolicyTransportResponse.model_validate_json(response.model_dump_json())
                        if (response.invocation_id != request.invocation_id
                                or response.request_sha256 != request.sha256
                                or response.manifest_sha256 != pinned.sha256):
                            raise PolicyHttpError("upstream_binding_mismatch")
                        counts["succeeded"] += 1
                        return Response(response.model_dump_json(), media_type="application/json",
                                        headers={"Cache-Control": "no-store"})
        except TimeoutError:
            counts["timeout"] += 1
            return error("upstream_timeout", 504)
        except asyncio.CancelledError:
            counts["cancelled"] += 1
            raise
        except PolicyHttpError as exc:
            counts["failed"] += 1
            return error(exc.code, 504 if exc.code == "http_timeout" else 502)
        except Exception:
            counts["failed"] += 1
            return error("upstream_failure", 502)
        finally:
            if pending is not None and not pending.done():
                pending.cancel()

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path, help="PolicyManifest model_dump_json file")
    parser.add_argument("--upstream", required=True, help="Loopback HTTP or HTTPS origin")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    manifest = PolicyManifest.model_validate_json(args.manifest.read_bytes())
    key = os.environ.get("POLICY_GATEWAY_API_KEY", "")
    upstream_key = os.environ.get("SGLANG_API_KEY")
    backend = SGLangChatBackend(base_url=args.upstream, manifest=manifest, api_key=upstream_key,
                               timeout_seconds=args.timeout)
    app = create_app(manifest=manifest, api_key=key, backend=backend, timeout_seconds=args.timeout)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
