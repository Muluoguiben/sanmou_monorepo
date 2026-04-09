"""Spider to crawl all skill (战法) data from sgmdtx.com and output RawBatchDocument YAML."""
from __future__ import annotations

import asyncio
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
DEFAULT_BUILD_ID = "v0WeVfocjIgrxCVSodE7G"

COLOR_MAP = {"orange": "橙", "purple": "紫", "blue": "蓝", "green": "绿"}

# sgmdtx ty field → our trigger_type
TY_MAP = {"主动": "主动战法", "被动": "被动战法", "指挥": "指挥战法", "追击": "追击战法"}

# sgmdtx tx field → our effect tags
TX_TAGS = {
    "兵刃": "兵刃",
    "谋略": "谋略",
    "防御": "防御",
    "辅助": "辅助",
    "控制": "控制",
    "文武": "文武兼备",
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "ingestion" / "raw" / "skills"


# ---------------------------------------------------------------------------
# Step 1: Discover skill names from the listing page
# ---------------------------------------------------------------------------
async def discover_skill_names() -> list[str]:
    """Load /zhanfa with Playwright and extract skill names from img[alt]."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel="chromium")
        page = await browser.new_page()
        await page.goto(f"{BASE_URL}/zhanfa", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000)
        names = await page.eval_on_selector_all(
            "img[alt]",
            "els => els.map(e => e.alt).filter(n => n && n.length > 0)",
        )
        await browser.close()
    return [n for n in names if 1 < len(n) <= 10 and n != "sgmdtx"]


async def discover_build_id() -> str:
    """Extract Next.js buildId from __NEXT_DATA__."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel="chromium")
        page = await browser.new_page()
        await page.goto(f"{BASE_URL}/zhanfa", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        data = await page.evaluate("() => window.__NEXT_DATA__")
        await browser.close()
    return data.get("buildId", DEFAULT_BUILD_ID)


# ---------------------------------------------------------------------------
# Step 2: Fetch individual skill JSON
# ---------------------------------------------------------------------------
async def fetch_skill_json(client, build_id: str, name: str) -> dict | None:
    encoded = urllib.parse.quote(name, safe="")
    url = f"{BASE_URL}/_next/data/{build_id}/zf/{encoded}.json?zf_name={encoded}"
    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("pageProps", {}).get("zf")
    except Exception as exc:
        print(f"  [WARN] Failed to fetch {name}: {exc}", file=sys.stderr)
        return None


async def fetch_all_skills(build_id: str, names: list[str], concurrency: int = 8) -> list[dict]:
    results: list[dict] = []
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:
        async def _fetch(name: str) -> None:
            async with sem:
                data = await fetch_skill_json(client, build_id, name)
                if data:
                    results.append(data)
                    print(f"  ✓ {name}")
                else:
                    print(f"  ✗ {name}")

        await asyncio.gather(*[_fetch(n) for n in names])

    return results


# ---------------------------------------------------------------------------
# Step 3: Convert to RawBatchDocument YAML format
# ---------------------------------------------------------------------------
def _infer_target_scope(desc: str) -> str | None:
    """Infer target scope from skill description text."""
    if "敌军全体" in desc or "全体敌军" in desc:
        return "敌军群体"
    if "友军全体" in desc or "全体友军" in desc:
        return "友军群体"
    if "敌军随机" in desc or "敌军单体" in desc:
        return "敌军单体"
    if "友军随机" in desc or "友军单体" in desc:
        return "友军单体"
    if "自身" in desc and "敌军" not in desc and "友军" not in desc:
        return "自身"
    return None


def skill_json_to_raw_record(zf: dict, captured_at: str) -> dict:
    """Convert a single sgmdtx skill JSON to a SkillRawRecord dict."""
    name = zf["name"]
    rarity = COLOR_MAP.get(zf.get("color", ""), None)

    ty = zf.get("ty", "")
    trigger_type = TY_MAP.get(ty, ty if ty else None)
    # skill_type is same as trigger_type for this game
    skill_type = trigger_type

    desc = zf.get("desc", "")
    mj_desc = zf.get("mj_desc", "")
    target_scope = _infer_target_scope(desc)

    # Effect tags from tx field
    tx = zf.get("tx", "")
    effect_tags = []
    if tx:
        mapped = TX_TAGS.get(tx, tx)
        effect_tags.append(mapped)

    # Probability
    gl = zf.get("gl", "")

    # Notes — max-level description first, initial as reference
    notes: list[str] = []
    if mj_desc:
        notes.append(f"效果（满级）：{mj_desc}")
        if desc and desc != mj_desc:
            notes.append(f"效果（初始）：{desc}")
    elif desc:
        notes.append(f"效果：{desc}")
    mj_gl = zf.get("mj_gl", "")
    if mj_gl:
        notes.append(f"满级发动概率：{mj_gl}")
    if gl:
        notes.append(f"初始发动概率：{gl}")

    # Troop compatibility from bz emojis
    bz = zf.get("bz", [])
    if bz:
        bz_str = "".join(bz)
        notes.append(f"适配兵种：{bz_str}")

    # Whether it's exclusive (wjj = true means it's a hero-exclusive skill)
    wjj = zf.get("wjj", False)
    if wjj:
        notes.append("自带战法（武将专属）")

    return {
        "canonical_name": name,
        "aliases": [],
        "rarity": rarity,
        "skill_type": skill_type,
        "trigger_type": trigger_type,
        "target_scope": target_scope,
        "effect_tags": effect_tags,
        "preferred_roles": [],
        "notes": notes,
        "source": {
            "source_url": f"https://www.sgmdtx.com/zf/{urllib.parse.quote(name, safe='')}",
            "source_site": SITE,
            "source_captured_at": captured_at,
        },
    }


def build_raw_batch_yaml(skills: list[dict], captured_at: str) -> dict:
    records = [skill_json_to_raw_record(s, captured_at) for s in skills]
    records.sort(key=lambda r: r["canonical_name"])
    return {"domain": "skill", "records": records}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    if httpx is None:
        print("ERROR: httpx is required. Install with: pip3 install httpx", file=sys.stderr)
        sys.exit(1)

    print("Step 1: Discovering skill names and build ID...")
    names, build_id = await asyncio.gather(discover_skill_names(), discover_build_id())
    print(f"  Found {len(names)} skills, buildId={build_id}")

    print(f"\nStep 2: Fetching skill details ({len(names)} skills)...")
    skills = await fetch_all_skills(build_id, names)
    print(f"  Successfully fetched {len(skills)}/{len(names)} skills")

    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    batch = build_raw_batch_yaml(skills, captured_at)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "sgmdtx-all-skills.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(batch, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\nDone! Wrote {len(batch['records'])} skill records to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
