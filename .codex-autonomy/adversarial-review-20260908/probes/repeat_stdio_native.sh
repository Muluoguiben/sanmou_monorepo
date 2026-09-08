#!/bin/sh
set -u
cd '/tmp/sanmou-cr-reopen-470d92c-MaNesZ/packages/pioneer-agent' || exit 2
mkdir -p '/tmp/sanmou-cr-reopen-470d92c-MaNesZ/stdio-runs'
bad=0
i=1
while [ "$i" -le 20 ]; do
  PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../sanmou-common/src:../qa-agent/src timeout 15 /tmp/sanmou-cr-20260908-venv/bin/python -B -m unittest tests.unit.test_agent_harness_timeouts.StdioDeadlineTests.test_silent_tool_call_closes_nested_client_and_is_not_reused tests.unit.test_agent_harness_timeouts.StdioDeadlineTests.test_silent_tool_failure_is_persisted_by_harness -v > '/tmp/sanmou-cr-reopen-470d92c-MaNesZ/stdio-runs/run-'"$i"'.log' 2>&1
  rc=$?
  printf 'iteration=%s exit=%s\n' "$i" "$rc"
  if [ "$rc" -ne 0 ]; then bad=$((bad+1)); fi
  i=$((i+1))
done
printf 'iterations=20 failed_iterations=%s\n' "$bad"
if [ "$bad" -ne 0 ]; then exit 1; fi
