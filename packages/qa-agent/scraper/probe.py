"""Quick probe script to inspect rendered page structure."""
from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright


async def probe(url: str) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"Loading {url} ...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Poll until body text grows (JS rendering data)
        for i in range(20):
            await page.wait_for_timeout(2000)
            text = await page.inner_text("body")
            text_len = len(text.strip())
            print(f"  [{i*2+2}s] body text length: {text_len}")
            if text_len > 1000:
                break

        # Dump page title
        title = await page.title()
        print(f"\nTitle: {title}")

        # Dump all text content (first 8000 chars)
        text = await page.inner_text("body")
        print(f"\n--- Body text ({len(text)} chars, showing first 8000) ---")
        print(text[:8000])

        # Check many selectors
        print("\n--- Selector counts ---")
        selectors = [
            "table", "tr", "td", "th",
            ".ant-table", ".ant-card", ".ant-list", ".ant-row", ".ant-col",
            "[class*=hero]", "[class*=wujiang]", "[class*=card]", "[class*=list]",
            "[class*=item]", "[class*=grid]", "[class*=avatar]", "[class*=name]",
            "a[href*=wujiang]", "a[href*=hero]",
            "img", "svg",
            "[data-testid]", "[data-id]", "[data-key]",
        ]
        for selector in selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"  {selector}: {count} elements")
            except Exception:
                pass

        # Dump first few links
        print("\n--- Links containing 'wujiang' or 'hero' ---")
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.href, text: e.innerText.trim()})).filter(e => e.href.includes('wujiang') || e.href.includes('hero')).slice(0, 30)"
        )
        for link in links:
            print(f"  {link['href']}  →  {link['text'][:40]}")

        # Check if there's a Next.js data script
        print("\n--- Script tags with data ---")
        scripts = await page.eval_on_selector_all(
            "script[id='__NEXT_DATA__']",
            "els => els.map(e => e.textContent.substring(0, 500))"
        )
        for s in scripts:
            print(f"  __NEXT_DATA__: {s}")

        # Check network-loaded JSON
        print("\n--- Page URL ---")
        print(f"  {page.url}")

        await browser.close()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.sgmdtx.com/wujiang"
    asyncio.run(probe(url))
