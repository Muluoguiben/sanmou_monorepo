"""Shared Playwright browser helpers for sgmdtx scraping."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, Page, async_playwright


@asynccontextmanager
async def launch_browser() -> AsyncGenerator[Browser, None]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            await browser.close()


async def fetch_rendered_page(url: str, wait_selector: str, timeout_ms: int = 15000) -> str:
    """Load a page with Playwright, wait for a selector, and return the HTML."""
    async with launch_browser() as browser:
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_selector(wait_selector, timeout=timeout_ms)
        html = await page.content()
        await page.close()
        return html


def fetch_rendered_page_sync(url: str, wait_selector: str, timeout_ms: int = 15000) -> str:
    """Synchronous wrapper for fetch_rendered_page."""
    return asyncio.run(fetch_rendered_page(url, wait_selector, timeout_ms))
