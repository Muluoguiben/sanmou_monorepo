---
name: sanmou-computer-use-safety
description: Apply Sanmou desktop GUI and NSLG client safety checks before @computer, Chrome, or Windows bridge interaction. Use when Codex needs real client observation, dry-run UI calibration, allowlist review, trace checks, or any low-risk game-window control.
---

# Sanmou Computer Use Safety

## Preconditions

- Read `.agent/skills/sanmou-client-control/SKILL.md` before touching the NSLG client.
- Prefer observe-only screenshot capture. An `observe_only` / Advisor-only source must never dispatch or synthesize executable input.
- Require explicit user approval before real clicks unless the action is already allowlisted, low risk, dry-run verified, and has a verifier.
- Never store account passwords, tokens, cookies, or private account screenshots in repo files, logs, or shared memory.

## Safety Checklist

1. Confirm target window identity with `list_windows` or process/window title evidence.
2. Capture a fresh screenshot and reject minimized, tiny, blank, stale, or wrong-window captures.
3. If clicking is requested, run dry-run/calibration first and record normalized coordinates plus screenshot evidence.
4. Check action risk:
   - low risk: close known popup, open harmless panel, claim clearly claimable reward after verifier exists
   - high risk: attack land, abandon land, lineup transfer, purchases, account/server/login actions
5. For real input, require allowlist, trace path, recovery plan, and kill-switch state.
6. Capture again after any action and verify the expected state change before continuing.

## Reporting

State whether the session stayed observe-only, dry-run, or dispatched real input. Include verifier result and any blocker. If safety prerequisites are missing, stop with a concrete missing item instead of guessing.
