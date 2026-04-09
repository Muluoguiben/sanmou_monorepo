#!/usr/bin/env python3
"""
知识库 Review 出题脚本

用法：
  # 默认：5 武将 + 5 战法，随机出题
  python3 scraper/review_quiz.py

  # 指定题数
  python3 scraper/review_quiz.py --heroes 8 --skills 5

  # 只出武将题
  python3 scraper/review_quiz.py --heroes 10 --skills 0

  # 只出战法题
  python3 scraper/review_quiz.py --heroes 0 --skills 10

  # 指定阵营/类型筛选
  python3 scraper/review_quiz.py --faction 蜀 --heroes 5 --skills 0
  python3 scraper/review_quiz.py --trigger 指挥 --heroes 0 --skills 5

  # 只出紫卡题
  python3 scraper/review_quiz.py --rarity 紫 --heroes 5 --skills 0

  # 带 API 校验（联网对比）
  python3 scraper/review_quiz.py --verify

  # 指定随机种子（可复现）
  python3 scraper/review_quiz.py --seed 42
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
import urllib.parse
from pathlib import Path

import yaml

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

KB_ROOT = Path(__file__).resolve().parent.parent / "knowledge_sources" / "profiles"
BUILD_ID = "v0WeVfocjIgrxCVSodE7G"
BASE_URL = "https://www.sgmdtx.com"

ZY_MAP = {"魏": "魏", "蜀": "蜀", "吴": "吴", "群": "群"}
COLOR_MAP = {"orange": "橙", "purple": "紫", "blue": "蓝"}
BZ_MAP = {"盾": "盾兵", "骑": "骑兵", "弓": "弓兵", "枪": "枪兵", "器": "器械"}
TY_MAP = {"主动": "主动", "被动": "被动", "指挥": "指挥", "追击": "追击"}


# ── 加载知识库 ──────────────────────────────────────────
def load_kb_heroes() -> dict[str, dict]:
    heroes = {}
    for f in ["wei", "shu", "wu", "qun", "minor", "other"]:
        path = KB_ROOT / "heroes" / f"{f}.yaml"
        if path.exists():
            for entry in yaml.safe_load(path.read_text("utf-8")) or []:
                heroes[entry["topic"]] = entry.get("structured_data", {})
    return heroes


def load_kb_skills() -> dict[str, dict]:
    skills = {}
    for f in ["active", "passive", "command", "pursuit"]:
        path = KB_ROOT / "skills" / f"{f}.yaml"
        if path.exists():
            for entry in yaml.safe_load(path.read_text("utf-8")) or []:
                skills[entry["topic"]] = entry.get("structured_data", {})
    return skills


# ── 出题格式 ────────────────────────────────────────────
def format_hero_question(idx: int, name: str, sd: dict) -> str:
    lines = [f"Q{idx}. 武将「{name}」"]

    faction = sd.get("faction", "?")
    rarity = sd.get("rarity", "?")
    troops = "、".join(sd.get("troop_types", [])) or "?"
    skills = "、".join(sd.get("signature_skills", [])) or "?"
    tags = "、".join(sd.get("role_tags", [])) or "无"
    lines.append(f"   阵营：{faction}  稀有度：{rarity}  兵种：{troops}")
    lines.append(f"   自带战法：{skills}  定位：{tags}")

    ba = sd.get("base_attributes") or {}
    ma = sd.get("max_attributes") or {}
    ga = sd.get("growth_attributes") or {}
    if ma:
        lines.append(
            f"   满级(Lv50)：武力{ma.get('military','?')} 智力{ma.get('intelligence','?')} "
            f"统率{ma.get('command','?')} 先攻{ma.get('initiative','?')}"
        )
    if ba:
        lines.append(
            f"   初始(Lv5)：武力{ba.get('military','?')} 智力{ba.get('intelligence','?')} "
            f"统率{ba.get('command','?')} 先攻{ba.get('initiative','?')}"
        )
    if ga:
        lines.append(
            f"   成长值：武力{ga.get('military','?')} 智力{ga.get('intelligence','?')} "
            f"统率{ga.get('command','?')} 先攻{ga.get('initiative','?')}"
        )

    notes = sd.get("notes", [])
    skill_effect = [n for n in notes if n.startswith("自带战法") and "满级" in n]
    bonds = [n for n in notes if n.startswith("缘分")]
    season = [n for n in notes if n.startswith("赛季")]
    suggest = [n for n in notes if n.startswith("推荐战法")]
    if skill_effect:
        lines.append(f"   {skill_effect[0][:200]}")
    if season:
        lines.append(f"   {season[0]}")
    if bonds:
        lines.append(f"   {bonds[0][:120]}")
    if suggest:
        lines.append(f"   {suggest[0][:120]}")

    return "\n".join(lines)


def format_skill_question(idx: int, name: str, sd: dict) -> str:
    lines = [f"Q{idx}. 战法「{name}」"]

    trigger = sd.get("trigger_type", "?")
    rarity = sd.get("rarity", "?")
    target = sd.get("target_scope") or "?"
    etags = "、".join(sd.get("effect_tags", [])) or "无"
    lines.append(f"   类型：{trigger}  稀有度：{rarity}  目标：{target}  效果标签：{etags}")

    notes = sd.get("notes", [])
    # 满级效果优先
    mj_desc = [n for n in notes if n.startswith("效果（满级）")]
    init_desc = [n for n in notes if n.startswith("效果（初始）") or n.startswith("效果：")]
    mj_prob = [n for n in notes if n.startswith("满级发动概率")]
    init_prob = [n for n in notes if n.startswith("初始发动概率") or n.startswith("发动概率")]

    if mj_desc:
        lines.append(f"   {mj_desc[0][:150]}")
    elif init_desc:
        lines.append(f"   {init_desc[0][:150]}")
    if mj_prob:
        lines.append(f"   {mj_prob[0]}")
    elif init_prob:
        lines.append(f"   {init_prob[0]}")

    exclusive = [n for n in notes if "武将专属" in n]
    if exclusive:
        lines.append(f"   ⚠ 自带战法（武将专属）")

    return "\n".join(lines)


# ── API 校验 ────────────────────────────────────────────
async def verify_hero(client, name: str, sd: dict) -> list[str]:
    encoded = urllib.parse.quote(name, safe="")
    url = f"{BASE_URL}/_next/data/{BUILD_ID}/wj/{encoded}.json?wj_name={encoded}"
    try:
        resp = await client.get(url, timeout=15)
        if resp.status_code != 200:
            return [f"API HTTP {resp.status_code}"]
        api = resp.json().get("pageProps", {}).get("wj", {})
    except Exception as exc:
        return [f"API 请求失败: {exc}"]

    issues = []
    # 阵营
    api_zy = ZY_MAP.get(api.get("zy", ""), "?")
    if api_zy != sd.get("faction", "?"):
        issues.append(f"阵营: API={api_zy} KB={sd.get('faction')}")
    # 稀有度
    api_rarity = COLOR_MAP.get(api.get("color", ""), "?")
    if api_rarity != sd.get("rarity", "?"):
        issues.append(f"稀有度: API={api_rarity} KB={sd.get('rarity')}")
    # 兵种
    api_bz = api.get("bz", "")
    api_troop = BZ_MAP.get(api_bz, api_bz + "兵" if api_bz else "?")
    if api_troop not in sd.get("troop_types", []):
        issues.append(f"兵种: API={api_troop} KB={sd.get('troop_types')}")
    # 自带战法
    api_skill = api.get("skill", "")
    if api_skill and api_skill not in sd.get("signature_skills", []):
        issues.append(f"自带战法: API={api_skill} KB={sd.get('signature_skills')}")
    # 满级属性验算
    ma = sd.get("max_attributes") or {}
    ba = sd.get("base_attributes") or {}
    ga = sd.get("growth_attributes") or {}
    if ba and ga:
        def _calc(base_key, growth_key):
            return round(ba.get(base_key, 0) + ga.get(growth_key, 0) * 45)
        for field, api_key in [("military", "wl"), ("intelligence", "zl"), ("command", "ts"), ("initiative", "xg")]:
            expected = _calc(field, field)
            actual = ma.get(field, 0)
            if expected != actual:
                issues.append(f"满级{field}: 算={expected} 存={actual}")
    return issues


async def verify_skill(client, name: str, sd: dict) -> list[str]:
    encoded = urllib.parse.quote(name, safe="")
    url = f"{BASE_URL}/_next/data/{BUILD_ID}/zf/{encoded}.json?zf_name={encoded}"
    try:
        resp = await client.get(url, timeout=15)
        if resp.status_code != 200:
            return [f"API HTTP {resp.status_code}"]
        api = resp.json().get("pageProps", {}).get("zf", {})
    except Exception as exc:
        return [f"API 请求失败: {exc}"]

    issues = []
    api_rarity = COLOR_MAP.get(api.get("color", ""), "?")
    if api_rarity != sd.get("rarity", "?"):
        issues.append(f"稀有度: API={api_rarity} KB={sd.get('rarity')}")
    api_ty = TY_MAP.get(api.get("ty", ""), "?")
    if api_ty != sd.get("trigger_type", "?"):
        issues.append(f"类型: API={api_ty} KB={sd.get('trigger_type')}")
    # 满级描述存在性
    notes_text = " ".join(sd.get("notes", []))
    api_mj = api.get("mj_desc", "")
    if api_mj and api_mj[:20] not in notes_text:
        issues.append(f"满级效果前20字未匹配")
    return issues


# ── 主流程 ──────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser(description="知识库 Review 出题")
    parser.add_argument("--heroes", type=int, default=5, help="武将题数 (default: 5)")
    parser.add_argument("--skills", type=int, default=5, help="战法题数 (default: 5)")
    parser.add_argument("--faction", type=str, default=None, help="筛选阵营: 魏/蜀/吴/群")
    parser.add_argument("--rarity", type=str, default=None, help="筛选稀有度: 橙/紫")
    parser.add_argument("--trigger", type=str, default=None, help="筛选战法类型: 主动/被动/指挥/追击")
    parser.add_argument("--verify", action="store_true", help="联网 API 校验")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    all_heroes = load_kb_heroes()
    all_skills = load_kb_skills()

    # 筛选
    hero_pool = list(all_heroes.items())
    skill_pool = list(all_skills.items())

    if args.faction:
        hero_pool = [(n, sd) for n, sd in hero_pool if sd.get("faction") == args.faction]
    if args.rarity:
        hero_pool = [(n, sd) for n, sd in hero_pool if sd.get("rarity") == args.rarity]
        skill_pool = [(n, sd) for n, sd in skill_pool if sd.get("rarity") == args.rarity]
    if args.trigger:
        skill_pool = [(n, sd) for n, sd in skill_pool if sd.get("trigger_type") == args.trigger]

    h_count = min(args.heroes, len(hero_pool))
    s_count = min(args.skills, len(skill_pool))
    h_picks = random.sample(hero_pool, h_count) if h_count > 0 else []
    s_picks = random.sample(skill_pool, s_count) if s_count > 0 else []

    total = h_count + s_count
    print("=" * 70)
    print(f"  知识库 Review（{total} 题：{h_count} 武将 + {s_count} 战法）")
    filters = []
    if args.faction:
        filters.append(f"阵营={args.faction}")
    if args.rarity:
        filters.append(f"稀有度={args.rarity}")
    if args.trigger:
        filters.append(f"战法类型={args.trigger}")
    if filters:
        print(f"  筛选条件：{', '.join(filters)}")
    if args.seed is not None:
        print(f"  随机种子：{args.seed}")
    print("=" * 70)

    idx = 1
    verify_results: list[tuple[str, list[str]]] = []

    if h_picks:
        print(f"\n{'─' * 30} 武将 {'─' * 30}\n")
        for name, sd in h_picks:
            print(format_hero_question(idx, name, sd))
            print()
            idx += 1

    if s_picks:
        print(f"\n{'─' * 30} 战法 {'─' * 30}\n")
        for name, sd in s_picks:
            print(format_skill_question(idx, name, sd))
            print()
            idx += 1

    # API 校验
    if args.verify:
        if httpx is None:
            print("\n⚠ --verify 需要 httpx，请安装: pip3 install httpx")
            return

        print(f"\n{'─' * 25} API 校验 {'─' * 25}\n")
        async with httpx.AsyncClient() as client:
            for name, sd in h_picks:
                issues = await verify_hero(client, name, sd)
                status = "✅" if not issues else f"⚠ {', '.join(issues)}"
                print(f"  武将 {name}: {status}")
                verify_results.append((name, issues))

            for name, sd in s_picks:
                issues = await verify_skill(client, name, sd)
                status = "✅" if not issues else f"⚠ {', '.join(issues)}"
                print(f"  战法 {name}: {status}")
                verify_results.append((name, issues))

        total_checks = len(verify_results)
        passed = sum(1 for _, issues in verify_results if not issues)
        print(f"\n  校验结果：{passed}/{total_checks} 通过")

    # 统计
    print(f"\n{'=' * 70}")
    print(f"  可用数据池：武将 {len(all_heroes)} 个 | 战法 {len(all_skills)} 个")
    if args.faction or args.rarity or args.trigger:
        print(f"  筛选后：武将 {len(hero_pool)} 个 | 战法 {len(skill_pool)} 个")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
