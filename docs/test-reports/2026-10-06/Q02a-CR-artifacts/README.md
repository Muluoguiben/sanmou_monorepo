# Q02a independent probes — preparation only

These reviewer-owned assets are frozen before implementation review. No tests,
provider, game, network or KB publish have been run by this preparation commit.
Syntax/JSON checks are not runtime results. The baseline e17d937 lacks Q02a;
future-contract failures on it are expected feature gaps, not new findings.

After receiving the immutable implementation SHA, the reviewer will run
`test_q02a_contract` with the selected source's `src/`, common `src/`, and this
artifact directory on PYTHONPATH, using explicit fake clients and a guarded
launcher. The real source root/code/tree and dependency origins must be recorded.
Never run it against whichever checkout happens to be current and label that as
the new code. Do not load `.env`, invoke a provider or write the formal KB.

The script checks public ChatAgent observations; it does not depend on the name
of a future private referent state. It intentionally does not use expected-failure
decorators. Some methods assert their retrieval setup, so fixture/setup failures
must be investigated and retained rather than misreported as product bugs.

v3 schema/manifest tests will be added after its actual versioned surface is
frozen. That adaptation must not relax this plan's v1/v2 immutability, source
identity, strict metadata, count/denominator or no-provider-quality boundaries.
