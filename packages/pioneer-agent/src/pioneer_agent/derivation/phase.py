from __future__ import annotations


def derive_phase_tag(hours_since_server_open: float, hours_until_settlement: float) -> str:
    if hours_since_server_open < 12:
        return "opening_sprint"
    if hours_until_settlement < 12:
        return "settlement_sprint"
    if hours_since_server_open < 36:
        return "growth_window"
    return "chapter_push"

