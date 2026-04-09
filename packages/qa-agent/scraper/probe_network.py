"""Probe network requests to find data API endpoints."""
from __future__ import annotations

import asyncio
import json
import sys

from playwright.async_api import async_playwright, Route, Request


async def probe_network(url: str) -> None:
    async with async_playwright() as pw:
        # Use full chromium instead of headless shell
        browser = await pw.chromium.launch(headless=True, channel="chromium")
        page = await browser.new_page()

        captured: list[dict] = []

        def on_request(request: Request) -> None:
            url_str = request.url
            # Capture API calls and JS chunks that might contain data
            if any(k in url_str for k in ["api", "json", "data", "wujiang", "hero", "graphql"]):
                captured.append({
                    "method": request.method,
                    "url": url_str,
                    "resource_type": request.resource_type,
                })

        page.on("request", on_request)

        # Also capture all responses with JSON content
        json_responses: list[dict] = []

        async def on_response(response) -> None:
            content_type = response.headers.get("content-type", "")
            url_str = response.url
            if "json" in content_type or "api" in url_str:
                try:
                    body = await response.text()
                    json_responses.append({
                        "url": url_str,
                        "status": response.status,
                        "content_type": content_type,
                        "body_preview": body[:1000],
                    })
                except Exception:
                    pass

        page.on("response", on_response)

        print(f"Loading {url} ...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000)

        print(f"\n--- Captured requests ({len(captured)}) ---")
        for req in captured:
            print(f"  [{req['method']}] {req['resource_type']}: {req['url'][:200]}")

        print(f"\n--- JSON responses ({len(json_responses)}) ---")
        for resp in json_responses:
            print(f"  [{resp['status']}] {resp['url'][:150]}")
            print(f"    content-type: {resp['content_type']}")
            print(f"    body: {resp['body_preview'][:300]}")
            print()

        # Also dump all JS chunk URLs
        print("--- All JS chunks loaded ---")
        all_scripts = await page.eval_on_selector_all(
            "script[src]",
            "els => els.map(e => e.src)"
        )
        for s in all_scripts:
            if "chunk" in s or "data" in s or "wujiang" in s:
                print(f"  {s}")

        # Try to find data in window/global state
        print("\n--- Window state keys ---")
        keys = await page.evaluate("""
            () => {
                const interesting = [];
                for (const key of Object.keys(window)) {
                    if (key.startsWith('__') || key.includes('data') || key.includes('store') || key.includes('state')) {
                        const val = window[key];
                        const type = typeof val;
                        const preview = type === 'object' ? JSON.stringify(val).substring(0, 200) : String(val).substring(0, 100);
                        interesting.push(`${key} (${type}): ${preview}`);
                    }
                }
                return interesting;
            }
        """)
        for k in keys:
            print(f"  {k}")

        # Check img src patterns
        print("\n--- Image src patterns (first 20) ---")
        imgs = await page.eval_on_selector_all(
            "img",
            "els => els.slice(0, 20).map(e => ({src: e.src, alt: e.alt, width: e.width, height: e.height}))"
        )
        for img in imgs:
            print(f"  {img.get('alt','')} | {img.get('width','')}x{img.get('height','')} | {img.get('src','')[:120]}")

        await browser.close()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.sgmdtx.com/wujiang"
    asyncio.run(probe_network(url))
