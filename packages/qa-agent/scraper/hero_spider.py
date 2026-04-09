"""Spider to crawl all hero data from sgmdtx.com and output RawBatchDocument YAML."""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SITE = "sgmdtx"
BASE_URL = "https://www.sgmdtx.com"
# This buildId changes on redeploys; we discover it at runtime.
DEFAULT_BUILD_ID = "v0WeVfocjIgrxCVSodE7G"

# sgmdtx field → our field mapping
ZY_MAP = {"魏": "魏国", "蜀": "蜀国", "吴": "吴国", "群": "群雄"}
BZ_MAP = {"盾": "盾兵", "骑": "骑兵", "弓": "弓兵", "枪": "枪兵", "器": "器械"}
COLOR_MAP = {"orange": "橙", "purple": "紫", "blue": "蓝", "green": "绿"}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "ingestion" / "raw" / "heroes"


# ---------------------------------------------------------------------------
# Step 1: Discover hero names from the listing page (needs Playwright)
# ---------------------------------------------------------------------------
async def discover_hero_names() -> list[str]:
    """Load /wujiang with Playwright and extract hero names from img[alt]."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel="chromium")
        page = await browser.new_page()
        await page.goto(f"{BASE_URL}/wujiang", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000)
        names = await page.eval_on_selector_all(
            "img[alt]",
            "els => els.map(e => e.alt).filter(n => n && n.length > 0)",
        )
        await browser.close()
    # Filter out non-hero entries (logos, icons)
    return [n for n in names if 1 < len(n) <= 10 and n != "sgmdtx"]


async def discover_build_id() -> str:
    """Extract Next.js buildId from __NEXT_DATA__ on the listing page."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel="chromium")
        page = await browser.new_page()
        await page.goto(f"{BASE_URL}/wujiang", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        data = await page.evaluate("() => window.__NEXT_DATA__")
        await browser.close()
    return data.get("buildId", DEFAULT_BUILD_ID)


# ---------------------------------------------------------------------------
# Step 2: Fetch individual hero JSON via Next.js data API (plain HTTP)
# ---------------------------------------------------------------------------
async def fetch_hero_json(client, build_id: str, name: str) -> dict | None:
    """Fetch a single hero's JSON from the Next.js data route."""
    encoded = urllib.parse.quote(name, safe="")
    url = f"{BASE_URL}/_next/data/{build_id}/wj/{encoded}.json?wj_name={encoded}"
    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("pageProps", {}).get("wj")
    except Exception as exc:
        print(f"  [WARN] Failed to fetch {name}: {exc}", file=sys.stderr)
        return None


async def fetch_skill_json(client, build_id: str, skill_name: str) -> dict | None:
    """Fetch a skill's JSON from the Next.js data route (works for signature skills too)."""
    encoded = urllib.parse.quote(skill_name, safe="")
    url = f"{BASE_URL}/_next/data/{build_id}/zf/{encoded}.json?zf_name={encoded}"
    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("pageProps", {}).get("zf")
    except Exception:
        return None


async def fetch_all_heroes(build_id: str, names: list[str], concurrency: int = 8) -> list[dict]:
    """Fetch all hero JSONs and their signature skill descriptions."""
    results: list[dict] = []
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:
        async def _fetch(name: str) -> None:
            async with sem:
                data = await fetch_hero_json(client, build_id, name)
                if data:
                    # Also fetch signature skill description
                    skill_name = data.get("skill", "")
                    if skill_name:
                        zf = await fetch_skill_json(client, build_id, skill_name)
                        if zf:
                            data["_skill_desc"] = zf.get("mj_desc") or zf.get("desc", "")
                            data["_skill_desc_init"] = zf.get("desc", "")
                            data["_skill_gl"] = zf.get("mj_gl") or zf.get("gl", "")
                    results.append(data)
                    print(f"  ✓ {name}")
                else:
                    print(f"  ✗ {name}")

        await asyncio.gather(*[_fetch(n) for n in names])

    return results


# ---------------------------------------------------------------------------
# Step 3: Convert to RawBatchDocument YAML format
# ---------------------------------------------------------------------------
def hero_json_to_raw_record(wj: dict, captured_at: str) -> dict:
    """Convert a single sgmdtx hero JSON to a HeroRawRecord dict."""
    name = wj["name"]
    faction = ZY_MAP.get(wj.get("zy", ""), None)
    rarity = COLOR_MAP.get(wj.get("color", ""), None)
    bz = wj.get("bz", "")
    troop_type = BZ_MAP.get(bz, bz + "兵" if bz else None)
    troop_types = [troop_type] if troop_type else []

    # Tags from the site (e.g. ["T1", "兵刃"])
    tags = wj.get("tags", [])
    role_tags = [t for t in tags if t]

    # Signature skill + description
    skill = wj.get("skill", "")
    signature_skills = [skill] if skill else []

    # Build notes — signature skill effect first
    notes: list[str] = []
    skill_desc = wj.get("_skill_desc", "")
    skill_desc_init = wj.get("_skill_desc_init", "")
    skill_gl = wj.get("_skill_gl", "")
    if skill and skill_desc:
        gl_part = f"（发动概率：{skill_gl}）" if skill_gl else ""
        notes.append(f"自带战法「{skill}」效果（满级）：{skill_desc}{gl_part}")
        if skill_desc_init and skill_desc_init != skill_desc:
            notes.append(f"自带战法「{skill}」效果（初始）：{skill_desc_init}")
    jb = wj.get("jb", [])
    if jb:
        bond_strs = [f"缘分「{b['name']}」：{'、'.join(b.get('member', []))}——{b.get('desc', '')}" for b in jb]
        notes.extend(bond_strs)

    suggest = wj.get("suggest_skills", [])
    if suggest:
        notes.append(f"推荐战法：{'、'.join(suggest)}")

    # Season tag
    sj = wj.get("sj", "")
    if sj:
        notes.append(f"赛季：{sj}")

    # Base attributes & growth & max-level (lv50 = base + growth * 50)
    def _safe_float(v: str) -> float:
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(v: str) -> int:
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    base_wl, base_zl, base_ts, base_xg = (
        _safe_int(wj.get("wl", "0")),
        _safe_int(wj.get("zl", "0")),
        _safe_int(wj.get("ts", "0")),
        _safe_int(wj.get("xg", "0")),
    )
    g_wl, g_zl, g_ts, g_xg = (
        _safe_float(wj.get("wl_incr", "0")),
        _safe_float(wj.get("zl_incr", "0")),
        _safe_float(wj.get("ts_incr", "0")),
        _safe_float(wj.get("xg_incr", "0")),
    )
    # Heroes start at Lv5, max Lv50 → 45 levels of growth
    max_wl = round(base_wl + g_wl * 45)
    max_zl = round(base_zl + g_zl * 45)
    max_ts = round(base_ts + g_ts * 45)
    max_xg = round(base_xg + g_xg * 45)

    notes.append(
        f"初始属性：武力{base_wl} 智力{base_zl} 统率{base_ts} 先攻{base_xg}"
    )
    notes.append(
        f"成长值：武力{wj.get('wl_incr','?')} 智力{wj.get('zl_incr','?')} "
        f"统率{wj.get('ts_incr','?')} 先攻{wj.get('xg_incr','?')}"
    )
    notes.append(
        f"满级属性(Lv50，Lv5起始+45级成长)：武力{max_wl} 智力{max_zl} 统率{max_ts} 先攻{max_xg}"
    )

    return {
        "canonical_name": name,
        "aliases": [],
        "faction": faction,
        "rarity": rarity,
        "troop_types": troop_types,
        "role_tags": role_tags,
        "base_attributes": {
            "military": base_wl,
            "intelligence": base_zl,
            "command": base_ts,
            "initiative": base_xg,
        },
        "growth_attributes": {
            "military": g_wl,
            "intelligence": g_zl,
            "command": g_ts,
            "initiative": g_xg,
        },
        "signature_skills": signature_skills,
        "notes": notes,
        "source": {
            "source_url": f"https://www.sgmdtx.com/wj/{urllib.parse.quote(name, safe='')}",
            "source_site": SITE,
            "source_captured_at": captured_at,
        },
    }


def build_raw_batch_yaml(heroes: list[dict], captured_at: str) -> dict:
    """Build the full RawBatchDocument structure."""
    records = [hero_json_to_raw_record(h, captured_at) for h in heroes]
    # Sort by name for stable output
    records.sort(key=lambda r: r["canonical_name"])
    return {"domain": "hero", "records": records}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    if httpx is None:
        print("ERROR: httpx is required. Install with: pip3 install httpx", file=sys.stderr)
        sys.exit(1)

    print("Step 1: Discovering hero names and build ID...")
    names, build_id = await asyncio.gather(discover_hero_names(), discover_build_id())
    print(f"  Found {len(names)} heroes, buildId={build_id}")

    print(f"\nStep 2: Fetching hero details ({len(names)} heroes)...")
    heroes = await fetch_all_heroes(build_id, names)
    print(f"  Successfully fetched {len(heroes)}/{len(names)} heroes")

    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    batch = build_raw_batch_yaml(heroes, captured_at)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "sgmdtx-all-heroes.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(batch, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\nDone! Wrote {len(batch['records'])} hero records to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
