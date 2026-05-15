from __future__ import annotations

from typing import Any


DETAIL_TABS = ("装备", "马匹", "兵书", "属性加点", "战法等级", "兵种适性")
MODES = ("pvp", "pve", "expedition")
SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "blocker": 4}


def apply_team_snapshot_judgements(state: Any) -> None:
    """Enrich observed teams with derived PVP/PVE/expedition readiness judgement."""
    for team in state.teams:
        judgement = evaluate_team_snapshot(team)
        snapshot = dict(team.get("team_snapshot") or {})
        snapshot["readiness_judgement"] = judgement
        snapshot["pvp_pve_basis_ready"] = judgement["basis_ready"]
        team["team_snapshot"] = snapshot
        team["readiness_judgement"] = judgement

        if team.get("team_id") == state.main_lineup.get("current_host_team_id"):
            state.main_lineup["team_snapshot"] = dict(snapshot)
            readiness = dict(state.main_lineup.get("team_readiness") or {})
            readiness["readiness_judgement"] = judgement
            readiness["pvp_pve_basis_ready"] = judgement["basis_ready"]
            state.main_lineup["team_readiness"] = readiness


def evaluate_team_snapshot(team: dict[str, Any]) -> dict[str, Any]:
    snapshot = team.get("team_snapshot") if isinstance(team.get("team_snapshot"), dict) else {}
    detail_completion = (
        snapshot.get("detail_completion")
        if isinstance(snapshot.get("detail_completion"), dict)
        else {}
    )
    heroes = [hero for hero in team.get("heroes", []) if isinstance(hero, dict)]
    facts = _facts(team, heroes, detail_completion)
    issues = _issues(team, heroes, facts)
    mode_judgement = {
        mode: _mode_judgement(mode, issues)
        for mode in MODES
    }
    basis_ready = not any(issue["severity"] == "blocker" for issue in issues)
    overall_status = _overall_status(issues)
    next_steps = _next_steps(issues)

    return {
        "source": "derivation.team_snapshot",
        "basis_ready": basis_ready,
        "overall_status": overall_status,
        "confidence": _confidence(issues, facts),
        "facts": facts,
        "issues": issues,
        "blocking_issues": [
            issue for issue in issues if issue["severity"] in {"blocker", "high"}
        ],
        "mode_judgement": mode_judgement,
        "next_steps": next_steps,
    }


def _facts(
    team: dict[str, Any],
    heroes: list[dict[str, Any]],
    detail_completion: dict[str, Any],
) -> dict[str, Any]:
    soldiers = _float_or_none(team.get("soldiers"))
    max_soldiers = _float_or_none(team.get("max_soldiers"))
    soldier_fill_ratio = (
        round(soldiers / max_soldiers, 4)
        if soldiers is not None and max_soldiers and max_soldiers > 0
        else None
    )
    stamina_values = [
        float(hero["stamina"])
        for hero in heroes
        if hero.get("stamina") is not None
    ]
    tactic_levels = [
        int(tactic["level"])
        for hero in heroes
        for tactic in hero.get("tactic_details", [])
        if isinstance(tactic, dict) and tactic.get("level") is not None
    ]
    max_tactic_levels = [
        int(tactic["max_level"])
        for hero in heroes
        for tactic in hero.get("tactic_details", [])
        if isinstance(tactic, dict) and tactic.get("max_level") is not None
    ]
    detailed_hero_count = sum(1 for hero in heroes if _hero_has_detail(hero))
    hero_count = len(heroes)

    return {
        "hero_count": hero_count,
        "detailed_hero_count": detailed_hero_count,
        "detail_coverage_ratio": round(detailed_hero_count / hero_count, 4) if hero_count else 0,
        "missing_detail_tabs": list(team.get("missing_detail_tabs") or []),
        "detail_completion": {
            tab: bool(detail_completion.get(tab))
            for tab in DETAIL_TABS
        },
        "soldier_fill_ratio": soldier_fill_ratio,
        "soldier_deficit": _float_or_zero(team.get("soldier_deficit")),
        "min_stamina": min(stamina_values) if stamina_values else None,
        "min_tactic_level": min(tactic_levels) if tactic_levels else None,
        "tactic_level_count": len(tactic_levels),
        "tactic_max_level_count": len(max_tactic_levels),
        "formation_active": team.get("formation_active"),
        "bond_active": team.get("bond_active"),
        "supply_ratio": _supply_ratio(team),
    }


def _issues(
    team: dict[str, Any],
    heroes: list[dict[str, Any]],
    facts: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    missing_detail_tabs = facts["missing_detail_tabs"]
    if missing_detail_tabs:
        issues.append(
            _issue(
                "missing_detail_tabs",
                "blocker",
                "缺少详情页字段：" + "、".join(missing_detail_tabs),
                MODES,
            )
        )
    if facts["hero_count"] < 3:
        issues.append(
            _issue("hero_count_low", "blocker", "队伍未识别满 3 名武将", MODES)
        )
    if facts["hero_count"] and facts["detailed_hero_count"] < facts["hero_count"]:
        issues.append(
            _issue(
                "partial_hero_detail_coverage",
                "blocker",
                f"仅 {facts['detailed_hero_count']}/{facts['hero_count']} 名武将有详情字段",
                MODES,
            )
        )
    if facts["formation_active"] is False:
        issues.append(_issue("formation_inactive", "high", "阵法未激活", MODES))
    if facts["bond_active"] is False:
        issues.append(_issue("bond_inactive", "medium", "缘分未激活", ("pvp", "pve")))

    soldier_fill_ratio = facts["soldier_fill_ratio"]
    if soldier_fill_ratio is not None:
        if soldier_fill_ratio < 0.9:
            issues.append(_issue("soldier_fill_low", "high", "兵力低于 90%", MODES))
        elif soldier_fill_ratio < 0.98:
            issues.append(_issue("soldier_fill_not_full", "medium", "兵力未满", MODES))

    min_tactic_level = facts["min_tactic_level"]
    if min_tactic_level is None and not missing_detail_tabs:
        issues.append(_issue("tactic_levels_missing", "blocker", "未识别战法等级", MODES))
    elif min_tactic_level is not None and min_tactic_level < 10:
        severity = "high" if min_tactic_level < 8 else "medium"
        issues.append(
            _issue(
                "tactic_level_below_10",
                severity,
                f"最低战法等级 {min_tactic_level}，未满 10",
                MODES,
            )
        )

    supply_ratio = facts["supply_ratio"]
    if supply_ratio is not None and supply_ratio < 0.8:
        issues.append(_issue("supply_low", "medium", "补给低于 80%", ("pve", "expedition")))

    min_stamina = facts["min_stamina"]
    if min_stamina is not None and min_stamina < 15:
        issues.append(_issue("stamina_low", "high", "体力不足一次常规行动", ("pve", "expedition")))

    for hero in heroes:
        issues.extend(_hero_detail_issues(hero))

    return _unique_issues(issues)


def _hero_detail_issues(hero: dict[str, Any]) -> list[dict[str, Any]]:
    if not _hero_has_detail(hero):
        return []
    name = str(hero.get("name") or "未知武将")
    issues: list[dict[str, Any]] = []
    if not hero.get("equipment"):
        issues.append(_issue("hero_equipment_missing", "medium", f"{name} 未识别装备", ("pvp", "pve")))
    if not hero.get("mount"):
        issues.append(_issue("hero_mount_missing", "medium", f"{name} 未识别马匹", ("pvp", "expedition")))
    if not hero.get("books"):
        issues.append(_issue("hero_books_missing", "medium", f"{name} 未识别兵书/韬略", ("pvp", "pve")))
    if not hero.get("attribute_points"):
        issues.append(_issue("hero_attribute_points_missing", "medium", f"{name} 未识别属性加点", ("pvp", "pve")))
    if not hero.get("tactic_details"):
        issues.append(_issue("hero_tactic_details_missing", "high", f"{name} 未识别战法等级", MODES))
    return issues


def _mode_judgement(mode: str, issues: list[dict[str, Any]]) -> dict[str, Any]:
    mode_issues = [issue for issue in issues if mode in issue["modes"]]
    max_severity = _max_severity(mode_issues)
    if max_severity == "blocker":
        status = "insufficient_basis"
        risk_level = "unknown"
    elif max_severity == "high":
        status = "not_ready"
        risk_level = "high"
    elif max_severity == "medium":
        status = "needs_review"
        risk_level = "medium"
    elif max_severity == "low":
        status = "usable"
        risk_level = "low"
    else:
        status = "ready"
        risk_level = "low"
    return {
        "status": status,
        "risk_level": risk_level,
        "issues": [issue["code"] for issue in mode_issues],
        "summary": _mode_summary(mode, status),
    }


def _overall_status(issues: list[dict[str, Any]]) -> str:
    max_severity = _max_severity(issues)
    if max_severity == "blocker":
        return "insufficient_basis"
    if max_severity == "high":
        return "not_ready"
    if max_severity == "medium":
        return "needs_review"
    if max_severity == "low":
        return "usable"
    return "ready"


def _next_steps(issues: list[dict[str, Any]]) -> list[str]:
    mapping = {
        "missing_detail_tabs": "继续查看队伍详情页，补齐缺失页签",
        "partial_hero_detail_coverage": "逐个进入 3 名武将详情页，补齐每名武将配置",
        "hero_count_low": "回到队伍总览重新识别完整阵容",
        "soldier_fill_low": "先补兵再判断战斗/远征",
        "soldier_fill_not_full": "补齐兵力缺口后再打高风险战斗",
        "tactic_level_below_10": "确认战法是否可升满 10 级",
        "tactic_levels_missing": "进入战法页识别每个战法等级",
        "formation_inactive": "检查阵法激活状态",
        "bond_inactive": "检查缘分激活状态",
        "stamina_low": "等待体力恢复或更换队伍",
        "supply_low": "补给恢复后再远征/连续战斗",
    }
    steps: list[str] = []
    for issue in issues:
        step = mapping.get(issue["code"])
        if step and step not in steps:
            steps.append(step)
    if not steps:
        steps.append("基础状态可用于 PVP/PVE/远征判断")
    return steps


def _issue(code: str, severity: str, message: str, modes: tuple[str, ...]) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "modes": list(modes),
    }


def _unique_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for issue in issues:
        key = (issue["code"], issue["message"])
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _max_severity(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "none"
    return max((issue["severity"] for issue in issues), key=lambda item: SEVERITY_RANK[item])


def _confidence(issues: list[dict[str, Any]], facts: dict[str, Any]) -> float:
    max_severity = _max_severity(issues)
    if max_severity == "blocker":
        return 0.42 if facts["detail_coverage_ratio"] > 0 else 0.28
    if max_severity == "high":
        return 0.72
    if max_severity == "medium":
        return 0.82
    return 0.9


def _mode_summary(mode: str, status: str) -> str:
    labels = {"pvp": "PVP", "pve": "PVE", "expedition": "远征"}
    status_text = {
        "insufficient_basis": "信息不足，不能可靠判断",
        "not_ready": "存在高风险问题，暂不建议使用",
        "needs_review": "可参考，但需要先处理风险点",
        "usable": "可用但仍有轻微风险",
        "ready": "基础状态完整，可用于判断",
    }
    return f"{labels[mode]}：{status_text[status]}"


def _hero_has_detail(hero: dict[str, Any]) -> bool:
    return any(
        bool(hero.get(key))
        for key in (
            "attributes",
            "attribute_points",
            "equipment",
            "mount",
            "books",
            "tactic_details",
            "soldier_specialties",
        )
    )


def _supply_ratio(team: dict[str, Any]) -> float | None:
    supply_ratio = _float_or_none(team.get("supply_ratio"))
    if supply_ratio is not None:
        return supply_ratio
    supply = _float_or_none(team.get("supply"))
    supply_max = _float_or_none(team.get("supply_max"))
    if supply is None or not supply_max:
        return None
    return round(supply / supply_max, 4)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_or_zero(value: Any) -> float:
    return _float_or_none(value) or 0.0
