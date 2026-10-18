# Q-E0 preparation independent review: initial source

Decision: REQUEST_CHANGES for one P2 fixed-repository boundary issue.
Author source `81c4a315d36e08979c76f1b9395045ed75cd3e76`; executed review
merge `7c0be267187604226940ab69212817e69827ccb0`, packages tree
`d954918d8218eb8b1b1c744aff75c7091c693cfd` exactly equal to author source.

## P2: inherited Git context can redirect the allowed-root metadata

prepare_e0_review.py `_git` passes no environment to subprocess.run, so a caller's
GIT_DIR/GIT_WORK_TREE/GIT_COMMON_DIR or GIT_CONFIG_* remains effective even with
cwd=REPOSITORY. `_output_root` trusts the resulting worktree list/check-ignore
without first checking show-toplevel against the script-determined repository.
Consequently the authorization metadata can describe another repository rather
than the fixed source repository; a valid current target can be rejected, and a
foreign repository's ignored data/agent_runs could be accepted when it exists.

Root confirmed the contract violation. Frozen synthetic probes use no foreign
repository, no new worktree and no out-of-scope output writes. They observe that
Git subprocesses implicitly inherit every injected context value and that a
synthetically wrong initial repository identity is not checked. Three assertions
fail on this source, including the WSL git.exe fallback's inherited environment.
This is not claimed as a real external-directory write reproduction.

Required repair: isolate inherited Git context for metadata calls, verify the
initial show-toplevel belongs to REPOSITORY, and retain existing Windows/WSL
fallback and legitimate registered-worktree output behavior. Do not weaken the
output restriction, source gates or independent assertions. This is a bounded
repository-selection fix, not a new hostile-concurrency framework.

Evidence: `qa-e0-prep-git-context-probes.py`, 3 failures/0 errors/0 skips;
`qa-e0-prep-independent-results/git-context-81c4-original-red.log`, 2808 bytes,
SHA256 `ae973facbe79de0174442a055256217fced2a7d53ccb9776d8795607ce482cb3`.
The original log remains immutable and must be rerun unchanged on the repair SHA.

## Other evidence, not a quality-gate promotion

- Previously frozen independent probes: 9 passed, including the actual
  _output_root path/fallback and ext4 ignored-directory writer boundary.
- Author's new test module, independently executed: 20 passed, 0 skips.
- Actual public verify: exit 0, fixed 34 KB YAML/153 production Python and
  original v4/claim-spans counts/identities; old whole-report hashes match the
  declared c30d4129...58858c / b9658bf8...32f0b6 values.
- The existing 440-test QA baseline and the final combined full suite are not
  represented by these 20 or 9 results; their separate runs remain required.
- Protocol's Chinese instructions, package/reply separation, unknown
  applicability and displayed-candidate-only judgments were read and agree with
  the contract. No human gold, independent holdout or Q07 quality pass exists.

All executed evidence is bound to the existing source above. No src/formal KB,
old fixtures/assertions, CI or dependency change; no real 50-task package,
provider/game/Q06 archive access, publication, push, master merge or deletion.
