"""自动核对考试：从 sgmdtx API 拉取样本数据，与知识库对比验证。"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.parse
from pathlib import Path

import httpx
import yaml

BUILD_ID = "v0WeVfocjIgrxCVSodE7G"
BASE = "https://www.sgmdtx.com"
KB_ROOT = Path(__file__).resolve().parent.parent / "knowledge_sources" / "profiles"

# ──────────────────────────────────────────────────
# 试题设计：10 道武将题 + 10 道战法题
# 覆盖：各阵营、各稀有度、各赛季、属性数值、缘分、兵种、
#       各战法类型、效果描述、发动概率、目标范围
# ──────────────────────────────────────────────────
HERO_SAMPLES = [
    "关羽",      # 蜀 橙 S1 — T1 兵刃大将
    "曹操",      # 魏 橙 S1 — 核心
    "孙权",      # 吴 橙 S1
    "吕布",      # 群 橙 S1 — 最高武力
    "诸葛亮2",   # 蜀 橙 S8 — 新赛季武将
    "张宁",      # 群 橙 S4
    "丁奉",      # 紫将
    "张梁",      # 紫将
    "乐进",      # 魏 橙 S3
    "周瑜",      # 吴 橙 S1
]

SKILL_SAMPLES = [
    "水淹七军",    # 主动 橙
    "空城计",      # 指挥 橙
    "十面埋伏",    # 主动 橙
    "固若金汤",    # 被动 橙
    "穷追不舍",    # 追击 橙
    "披坚执锐",    # 指挥 橙
    "夜袭",        # 追击 紫
    "强袭",        # 主动 紫
    "烈火焚营",    # 主动 橙
    "同舟共济",    # 指挥 橙
]


def load_kb_heroes() -> dict[str, dict]:
    heroes = {}
    for f in ["wei", "shu", "wu", "qun", "other"]:
        path = KB_ROOT / "heroes" / f"{f}.yaml"
        if path.exists():
            for entry in yaml.safe_load(path.read_text("utf-8")) or []:
                heroes[entry["topic"]] = entry
    return heroes


def load_kb_skills() -> dict[str, dict]:
    skills = {}
    for f in ["active", "passive", "command", "pursuit"]:
        path = KB_ROOT / "skills" / f"{f}.yaml"
        if path.exists():
            for entry in yaml.safe_load(path.read_text("utf-8")) or []:
                skills[entry["topic"]] = entry
    return skills


async def fetch_api_hero(client: httpx.AsyncClient, name: str) -> dict | None:
    encoded = urllib.parse.quote(name, safe="")
    url = f"{BASE}/_next/data/{BUILD_ID}/wj/{encoded}.json?wj_name={encoded}"
    resp = await client.get(url, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("pageProps", {}).get("wj")
    return None


async def fetch_api_skill(client: httpx.AsyncClient, name: str) -> dict | None:
    encoded = urllib.parse.quote(name, safe="")
    url = f"{BASE}/_next/data/{BUILD_ID}/zf/{encoded}.json?zf_name={encoded}"
    resp = await client.get(url, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("pageProps", {}).get("zf")
    return None


# ──────────────────────────────────────────────────
# 核对逻辑
# ──────────────────────────────────────────────────
ZY_MAP = {"魏": "魏", "蜀": "蜀", "吴": "吴", "群": "群"}
COLOR_MAP = {"orange": "橙", "purple": "紫", "blue": "蓝"}
BZ_MAP = {"盾": "盾兵", "骑": "骑兵", "弓": "弓兵", "枪": "枪兵", "器": "器械"}
TY_MAP = {"主动": "主动", "被动": "被动", "指挥": "指挥", "追击": "追击"}


def check_hero(q_num: int, name: str, api: dict, kb: dict) -> list[str]:
    """Compare API data vs KB entry for a hero. Return list of issues."""
    issues = []
    sd = kb.get("structured_data", {})
    notes = sd.get("notes", [])
    notes_text = " ".join(notes)

    # Q: 阵营
    api_zy = ZY_MAP.get(api.get("zy", ""), "?")
    kb_zy = sd.get("faction", "?")
    if api_zy != kb_zy:
        issues.append(f"阵营不匹配: API={api_zy} KB={kb_zy}")

    # Q: 稀有度
    api_rarity = COLOR_MAP.get(api.get("color", ""), "?")
    kb_rarity = sd.get("rarity", "?")
    if api_rarity != kb_rarity:
        issues.append(f"稀有度不匹配: API={api_rarity} KB={kb_rarity}")

    # Q: 兵种
    api_bz = api.get("bz", "")
    api_troop = BZ_MAP.get(api_bz, api_bz + "兵" if api_bz else "?")
    kb_troops = sd.get("troop_types", [])
    if api_troop not in kb_troops:
        issues.append(f"兵种不匹配: API={api_troop} KB={kb_troops}")

    # Q: 自带战法
    api_skill = api.get("skill", "")
    kb_skills = sd.get("signature_skills", [])
    if api_skill and api_skill not in kb_skills:
        issues.append(f"自带战法不匹配: API={api_skill} KB={kb_skills}")

    # Q: 四维属性（检查 notes 中是否包含）
    api_wl = api.get("wl", "?")
    api_zl = api.get("zl", "?")
    api_ts = api.get("ts", "?")
    api_xg = api.get("xg", "?")
    attr_str = f"武力{api_wl} 智力{api_zl} 统率{api_ts} 先攻{api_xg}"
    if attr_str not in notes_text:
        issues.append(f"四维属性未找到: 期望含 '{attr_str}'")

    # Q: 成长值
    api_wl_g = api.get("wl_incr", "?")
    api_zl_g = api.get("zl_incr", "?")
    growth_str = f"武力{api_wl_g} 智力{api_zl_g}"
    if growth_str not in notes_text:
        issues.append(f"成长值未找到: 期望含 '{growth_str}'")

    # Q: 缘分名称
    api_jb = api.get("jb", [])
    for bond in api_jb[:2]:  # 检查前两个缘分
        bond_name = bond.get("name", "")
        if bond_name and bond_name not in notes_text:
            issues.append(f"缘分「{bond_name}」未找到")

    # Q: 赛季
    api_sj = api.get("sj", "")
    if api_sj and f"赛季：{api_sj}" not in notes_text:
        issues.append(f"赛季不匹配: API={api_sj}")

    return issues


def check_skill(q_num: int, name: str, api: dict, kb: dict) -> list[str]:
    """Compare API data vs KB entry for a skill."""
    issues = []
    sd = kb.get("structured_data", {})
    notes = sd.get("notes", [])
    notes_text = " ".join(notes)

    # Q: 稀有度
    api_rarity = COLOR_MAP.get(api.get("color", ""), "?")
    kb_rarity = sd.get("rarity", "?")
    if api_rarity != kb_rarity:
        issues.append(f"稀有度不匹配: API={api_rarity} KB={kb_rarity}")

    # Q: 战法类型
    api_ty = TY_MAP.get(api.get("ty", ""), "?")
    kb_trigger = sd.get("trigger_type", "?")
    if api_ty != kb_trigger:
        issues.append(f"类型不匹配: API={api_ty} KB={kb_trigger}")

    # Q: 效果描述（检查 notes 中是否包含原始 desc 的前 20 个字）
    api_desc = api.get("desc", "")
    if api_desc:
        desc_head = api_desc[:20]
        if desc_head not in notes_text:
            issues.append(f"效果描述开头未找到: '{desc_head}...'")

    # Q: 发动概率
    api_gl = api.get("gl", "")
    if api_gl and f"发动概率：{api_gl}" not in notes_text:
        issues.append(f"发动概率不匹配: API={api_gl}")

    # Q: 满级描述存在性
    api_mj = api.get("mj_desc", "")
    if api_mj and api_mj != api_desc:
        if "满级效果" not in notes_text:
            issues.append("缺少满级效果描述")

    return issues


async def run_quiz():
    kb_heroes = load_kb_heroes()
    kb_skills = load_kb_skills()

    total_checks = 0
    total_pass = 0
    total_fail = 0
    all_issues: list[str] = []

    async with httpx.AsyncClient() as client:
        print("=" * 70)
        print("  武将 & 战法 基础信息核对考试")
        print("=" * 70)

        # ── 武将题 ──
        print("\n【第一部分】武将核对（10 题）\n")
        for i, name in enumerate(HERO_SAMPLES, 1):
            api = await fetch_api_hero(client, name)
            kb = kb_heroes.get(name)

            if not api:
                print(f"  Q{i}. {name} — ❌ API 获取失败")
                total_fail += 1
                total_checks += 1
                continue
            if not kb:
                print(f"  Q{i}. {name} — ❌ 知识库中未找到")
                total_fail += 1
                total_checks += 1
                continue

            issues = check_hero(i, name, api, kb)
            sd = kb.get("structured_data", {})

            # 打印题目和答案
            print(f"  Q{i}. {name}")
            print(f"      阵营: {sd.get('faction','?')} | 稀有度: {sd.get('rarity','?')} | 兵种: {sd.get('troop_types',[])} | 自带: {sd.get('signature_skills',[])}")
            print(f"      API: zy={api.get('zy')} color={api.get('color')} bz={api.get('bz')} skill={api.get('skill')}")
            print(f"      四维: 武{api.get('wl')} 智{api.get('zl')} 统{api.get('ts')} 行{api.get('xg')} | 赛季: {api.get('sj')}")

            check_count = 8  # 阵营+稀有度+兵种+战法+四维+成长+缘分+赛季
            pass_count = check_count - len(issues)
            total_checks += check_count
            total_pass += pass_count
            total_fail += len(issues)

            if issues:
                print(f"      ⚠️  {len(issues)} 项不一致:")
                for iss in issues:
                    print(f"         - {iss}")
                all_issues.extend([f"武将 {name}: {iss}" for iss in issues])
            else:
                print(f"      ✅ 全部 {check_count} 项一致")
            print()

        # ── 战法题 ──
        print("\n【第二部分】战法核对（10 题）\n")
        for i, name in enumerate(SKILL_SAMPLES, 1):
            api = await fetch_api_skill(client, name)
            kb = kb_skills.get(name)

            if not api:
                print(f"  Q{i+10}. {name} — ❌ API 获取失败")
                total_fail += 1
                total_checks += 1
                continue
            if not kb:
                print(f"  Q{i+10}. {name} — ❌ 知识库中未找到")
                total_fail += 1
                total_checks += 1
                continue

            issues = check_skill(i + 10, name, api, kb)
            sd = kb.get("structured_data", {})

            print(f"  Q{i+10}. {name}")
            print(f"      类型: {sd.get('trigger_type','?')} | 稀有度: {sd.get('rarity','?')} | 目标: {sd.get('target_scope','?')}")
            print(f"      API: ty={api.get('ty')} color={api.get('color')} gl={api.get('gl')}")
            api_desc = api.get("desc", "")
            print(f"      效果(前50字): {api_desc[:50]}...")

            check_count = 5  # 稀有度+类型+效果+概率+满级
            pass_count = check_count - len(issues)
            total_checks += check_count
            total_pass += pass_count
            total_fail += len(issues)

            if issues:
                print(f"      ⚠️  {len(issues)} 项不一致:")
                for iss in issues:
                    print(f"         - {iss}")
                all_issues.extend([f"战法 {name}: {iss}" for iss in issues])
            else:
                print(f"      ✅ 全部 {check_count} 项一致")
            print()

    # ── 汇总 ──
    print("=" * 70)
    print(f"  考试结果：{total_pass}/{total_checks} 项通过  ({total_pass/total_checks*100:.1f}%)")
    print(f"  通过: {total_pass}  |  不一致: {total_fail}")
    print("=" * 70)

    if all_issues:
        print("\n  不一致项汇总:")
        for iss in all_issues:
            print(f"    - {iss}")

    return total_fail == 0


if __name__ == "__main__":
    ok = asyncio.run(run_quiz())
    sys.exit(0 if ok else 1)
