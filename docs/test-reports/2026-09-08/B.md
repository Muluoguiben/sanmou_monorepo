# Task B self-test — R05 / R08

Status: implementation verified offline; unified adversarial CR pending.

Implementation commit: 5d635e45f768d10528a172533d4ace74306df8a1. This follow-up only aligns the report filename with the coordinator's manifest and updates the Task B TODO link; the tested code/test blobs below are unchanged.

## Scope and tested tree

- Task: 01a07f0b-149e-7160-a896-551165a702a0.
- Worktree: C:/Users/Lan/.codex/worktrees/dccc/sanmou_monorepo.
- WSL view: /mnt/c/Users/Lan/.codex/worktrees/dccc/sanmou_monorepo.
- Feature: feat/review-b-public-payload-roster.
- Start: d377ef8bbaa69e6b25928255eac0cb62714e82f8, initially clean and detached; ancestry check exit 0.
- Frozen charter/report read from coordinator worktree at documentation commit dd76d601f6f40d3e4fceaf10cdd360d78af88cb2; that commit was not merged.
- Owned code: mcp_server/privacy.py, mcp_server/service.py, perception/domains/merge.py; two new unit-test modules; this report and only the Task B TODO section.
- No edits to contracts.py, other tasks' code, shared environment/auth, or master.

Tests ran on the start commit plus these final code/test blobs. Report/TODO are added after testing and do not alter tested code. The containing commit is supplied with its immutable URL in delivery, avoiding a self-referential SHA.

| File under packages/pioneer-agent | Git blob |
|---|---|
| src/pioneer_agent/mcp_server/privacy.py | 1e9a55f10c61c8e64fdf56b0fab7ce1808e7d6db |
| src/pioneer_agent/mcp_server/service.py | ae69a0cef9165b0a4408affa8a0e874e16404a0a |
| src/pioneer_agent/perception/domains/merge.py | fddaf7273cd9855eebb9ca99bfde56c7fc83e5ad |
| tests/unit/test_game_mcp_public_payload.py | 4ef40626415415eb1e1864da84e6fd5fb8a8f077 |
| tests/unit/test_team_roster_merge.py | 00424c95b5fa9ce323dadd4817beee8ac50b2a4f |

## Fix and regression evidence

R05: runtime mappings use finite domain-specific object shapes rather than recursively admitting one global key set. Output retains map filters, selected resources/levels, visible/candidate land facts, resource type, occupation pending/countdown, battle troop measurements and parse/verification uncertainty, chapter tasks, resources/currencies and documented timing fields. Report/candidate/offline-action risks retain level and confirmation_required. Nested equipment attributes and readiness judgements survive. Tool input schemas and sanmou-game/v1 are unchanged.

Privacy negatives cover unknown metadata, misplaced otherwise-public keys, mappings substituted for scalars, owner/account names, raw battle/map screen notes, private paths/URIs/base64-like strings, collection/string bounds, and hostile paths appended to legitimate game labels. Only fixed slash-containing readiness labels are recognized as game prose; generic path rejection remains. Screen/button pixel boxes remain private; game-map coordinates are public decision context.

test_real_domain_builders_survive_service_and_canonical_consumer constructs synthetic MapLandDetection, BattleReportDetection, ChapterPanelDetection and PageDetection, calls production fragment builders, then GameMCPService/FastMCP and InProcessMcpClient/validate_game_response. It checks state/report parity, risk, unknown occupation, absent action-verifier authority and one provider refresh. Existing official ClientSession/stdio_client initialize/list/call smoke also passes in the focused suite.

R08: complete team panels replace each observed team's roster. Only uniquely matched retained heroes inherit details. Changed membership invalidates aggregate readiness, effects, old detail metadata and container stamina. Details remain patches; removed/ambiguous identities and older snapshots are rejected together with their aggregate readiness. Other teams/unrelated fields survive. Tests cover A/B/C -> A/B/D, unchanged/reordered/faction-alias rosters, ambiguous aliases, empty rosters, retained-member patches, removed-member late patches, older detail/panel observations and non-mutation.

## Environment and exact commands

Windows host, PowerShell orchestration; tests in WSL Ubuntu, Python 3.12.3 (GCC 13.3.0), Linux 6.6.87.2-microsoft-standard-WSL2, glibc 2.39. Final venv: /tmp/sanmou-b-isolated-01a07f0b, no system site packages or editable installs.

Dependencies: pydantic 2.13.5, pydantic-core 2.46.5, PyYAML 6.0.3, mcp 1.29.1, Pillow 12.3.0, cryptography 46.0.7, requests 2.34.2, FastAPI 0.141.1, Starlette 1.6.0, uvicorn 0.52.4, python-multipart 0.0.32, httpx 0.28.1, google-genai 2.22.0. These satisfy Pioneer constraints. No real provider was called; this does not establish compatibility with QA's separate google-genai<2 dependency constraint.

Setup (exit 0):

~~~bash
python3 -m venv --without-pip /tmp/sanmou-b-isolated-01a07f0b
# Requirements are Pioneer pyproject project.dependencies, excluding the
# local sanmou-common package, plus httpx. No global environment modifications.
python3 -m pip --python /tmp/sanmou-b-isolated-01a07f0b/bin/python install \
  --proxy http://127.0.0.1:7897 --timeout 20 --retries 1 \
  -r /tmp/sanmou-b-requirements.txt
~~~

Final tests:

~~~bash
cd /mnt/c/Users/Lan/.codex/worktrees/dccc/sanmou_monorepo/packages/pioneer-agent
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
PYTHONPATH=src:../sanmou-common/src:tests/unit \
/tmp/sanmou-b-isolated-01a07f0b/bin/python -m unittest \
  test_game_mcp_public_payload test_team_roster_merge \
  test_team_detail_domain test_team_panel_domain \
  test_game_mcp_contract test_game_mcp_server test_game_mcp_service \
  test_game_mcp_live_provider test_agent_harness_game_mcp_integration \
  -v > /tmp/sanmou-b-focused-isolated.log 2>&1

PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
PYTHONPATH=src:../sanmou-common/src \
/tmp/sanmou-b-isolated-01a07f0b/bin/python -m unittest discover \
  -s tests -p "test_*.py" -v > /tmp/sanmou-b-package-isolated.log 2>&1
~~~

| Run | Exit | Pass | Fail/error | Skip | Output |
|---|---:|---:|---:|---:|---|
| Final focused | 0 | 50 | 0 | 0 | Ran 50 tests in 7.113s; OK |
| Final Pioneer package | 0 | 787 | 0 | 0 | Ran 787 tests in 31.264s; OK |
| Baseline counterexamples | 1 | 0 | 1 failure + 1 error | 0 | Missing map_land_filter; roster A/B/C/D |

Baseline replay loads only the original three modules in a temporary Python process, without worktree edits. Run this with the same venv/PYTHONPATH and package cwd:

~~~python
import importlib, subprocess, sys, unittest
modules = {
    "pioneer_agent.mcp_server.privacy": "packages/pioneer-agent/src/pioneer_agent/mcp_server/privacy.py",
    "pioneer_agent.mcp_server.service": "packages/pioneer-agent/src/pioneer_agent/mcp_server/service.py",
    "pioneer_agent.perception.domains.merge": "packages/pioneer-agent/src/pioneer_agent/perception/domains/merge.py",
}
for name, path in modules.items():
    module = importlib.import_module(name)
    source = subprocess.check_output([
        "git.exe", "show", "d377ef8bbaa69e6b25928255eac0cb62714e82f8:" + path,
    ])
    exec(compile(source, path, "exec"), module.__dict__)
suite = unittest.defaultTestLoader.loadTestsFromNames([
    "test_game_mcp_public_payload.GameMCPPublicPayloadTests.test_real_domain_builders_survive_service_and_canonical_consumer",
    "test_team_roster_merge.TeamRosterMergeTests.test_roster_replacement_keeps_only_retained_hero_details",
])
sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
~~~

## Initial failures and verification limits

- Default exec, Node and apply_patch failed during sandbox setup. Scoped reviewed elevated exec and the installed native Codex apply-patch entry worked. One broad fixture restore was rejected because it lacked a conditional clean-tree check; no rejected operation executed.
- Initial focused runs exposed strict synthetic map-input requirements and unrelated-field compatibility; fixed without changing existing tests. A new deep regression exposed slash-containing generated readiness prose; fixed game labels survive, appended paths still fail.
- Initial package: 783 tests, 8 errors, 6 skips. One error was the new test discovery import; fixed. Seven were existing eval digest errors because Windows checkout changed two hash-bound JSON files from LF to CRLF. Six were missing FastAPI in the initial system-site venv.
- Before final tests, those two scenario transcripts were verified clean and byte-equal to HEAD after CRLF normalization, then restored to exact Git blob bytes. No manifest/hash expectations or semantic fixture content changed. F owns the permanent scoped LF rule; B does not commit that change.
- After testing, both transcript files were restored to their original Windows CRLF working-copy bytes. Neither appears in the implementation diff; canonical committed fixture bytes remain LF.
- API dependencies installed in a pure task venv eliminated all six skips. Direct PyPI download initially timed out; the proxy install succeeded.
- No deleted tests, weakened validation, changed preexisting expectations, shared auth/.env edits, new screenshots, external model calls, game capture or input. New perception evidence is synthetic and exercises production builders, not visual accuracy.
- Full-package tests include existing synthetic/offline replay and fixture-based image tests. They do not prove live-client correctness. No new real image was captured/imported and no external holdout oracle was read.
- Authority remains none; proposals executable=false; normal --execute and live replay remain disabled. No safe live controller/broker, provider accuracy, native Windows runtime or release readiness claim.
- C confirmed its timer fixes need no new public fields. QA's six-tool contract is untouched; QA full-package testing is outside this task. Unified component/combined-tree CR remains required.
