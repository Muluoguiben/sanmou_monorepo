# NSLG Client Evidence Worklog

## 2026-05-20 Client Evidence Bundle Round35

Goal slice: preserve current offline NSLG client extraction state as a qa-agent import-planning evidence bundle.

Actions:
- Read repo-local instructions from `.agent/AGENTS.md` and `packages/qa-agent/CLAUDE.md`.
- Treated WSL `/home/lan/projects/sanmou_monorepo` as the authoritative current worktree after the incomplete `C:\home` recovery.
- Reviewed existing client ingestion artifacts:
  - package manifest
  - LuaScripts TextAsset catalog
  - LuaScripts crypto evidence
  - NEP2 LuaScripts/protector evidence
  - decoded hero staging audit
- Added `src/qa_agent/ingestion/client_evidence_bundle.py`.
- Added CLI `src/qa_agent/app/build_client_evidence_bundle.py`.
- Added tests in `tests/test_client_evidence_bundle.py`.
- Generated `ingestion/raw/client_packages/nslg-client-evidence-bundle-round35.yaml`.
- Updated `ingestion/raw/client_packages/README.md` with the new artifact and rebuild command.

Result:
- Bundle schema: `nslg.client_evidence_bundle.v1`.
- Source id: `nslg-client-offline-bundle-round35`.
- Artifact count: 5.
- Evidence ref count: 317.
- Client app version: `1.29.0`.
- `safe_for_publish=false`.
- `publishable_knowledge_entries=0`.
- `normalized_staging_entries=63`.
- Decoder/static target artifacts:
  - `luascripts_textasset_catalog`
  - `luascripts_crypto_evidence`
  - `nep2_luascripts_static_evidence`
- Blocker count: 15.

Verification:
- Targeted client ingestion tests passed:
  - `PYTHONPATH=src python3 -m unittest tests.test_client_evidence_bundle tests.test_client_package_scan tests.test_client_decoded tests.test_client_luascripts tests.test_client_nep2_luascripts tests.test_client_lua_crypto -v`
  - 16 tests passed.
- Full qa-agent tests passed:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v`
  - 190 tests passed.

Hashes:
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round35.yaml`
  - SHA-256 `26f11804d0e087982cf05ebba2699124d49eb04485554404241a4a0c78fdf3e0`
- `src/qa_agent/ingestion/client_evidence_bundle.py`
  - SHA-256 `a52be14262ee6a9b8bf4c8429c1ab559dd66308860cfe175103d5f96c5e2c068`
- `src/qa_agent/app/build_client_evidence_bundle.py`
  - SHA-256 `686b0396c206bdb0a8de4c921d64c2d749a859363805cb86cd042632317f9fc9`
- `tests/test_client_evidence_bundle.py`
  - SHA-256 `fda4af0c16e779724d99f4e5fb00447fc86f9fec08d2bd987c1a6a3251b5be11`

Interpretation:
- This slice does not decode protected LuaScripts or `.ns` payloads.
- It makes the current offline extraction state durable and queryable as an evidence chain.
- The bundle is intentionally not publishable: normalized client-decoded heroes need review, and LuaScripts/NEP2 evidence remains decoder-target material.

Next step:
- Continue offline/static only.
- Highest-value path is to narrow or decode the LuaScripts/NEP2 protected payload path, then convert readable domain records into reviewed staging entries with stable `source_ref` / `evidence_ref`.

## 2026-05-20 Client Import Queue Round36

Goal slice: turn the current offline client evidence bundle into a sorted review/decoder queue for qa-agent import planning.

Actions:
- Read `.codex-autonomy/state.json`, `.codex-autonomy/WORKLOG.md`, project instructions, and qa-agent package instructions before acting.
- Added `src/qa_agent/ingestion/client_import_queue.py`.
- Added CLI `src/qa_agent/app/build_client_import_queue.py`.
- Added tests in `tests/test_client_import_queue.py`.
- Generated `ingestion/raw/client_packages/nslg-client-import-queue-round36.yaml`.
- Updated `ingestion/raw/client_packages/README.md` with the round36 artifact and rebuild command.

Result:
- Queue schema: `nslg.client_import_queue.v1`.
- Source id: `nslg-client-import-queue-round36`.
- Queue item count: 87.
- Queue types:
  - `decoded_hero_review`: 63.
  - `luascripts_decoder_target`: 16.
  - `lua_crypto_decoder_target`: 4.
  - `nep2_static_trace_target`: 4.
- Readiness:
  - `needs_manual_review`: 63.
  - `blocked_pending_decoder`: 20.
  - `static_trace_target`: 4.
- `safe_for_publish=false`.
- `auto_publish_allowed=false`.
- `publishable_now_count=0`.
- Queue blocker count: 145.

Verification:
- Targeted client ingestion tests passed:
  - `PYTHONPATH=src python3 -m unittest tests.test_client_import_queue tests.test_client_evidence_bundle tests.test_client_package_scan tests.test_client_decoded tests.test_client_luascripts tests.test_client_nep2_luascripts tests.test_client_lua_crypto -v`
  - 18 tests passed.
- Full qa-agent tests passed:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v`
  - 192 tests passed.
- Sanitization check passed:
  - `rg -n -e "C:" -e "/home/" -e "/Users/" -e "password" -e "token" -e "server_id" -e "role_id" -e "mail" -e "chat" ingestion/raw/client_packages/nslg-client-import-queue-round36.yaml`
  - Only the guardrail sentence mentioning forbidden `password/token` storage matched.

Hashes:
- `ingestion/raw/client_packages/nslg-client-import-queue-round36.yaml`
  - SHA-256 `8161e9e4890167ded32410fe177c5b402ec809d84b83633be5677d18789d540b`
- `src/qa_agent/ingestion/client_import_queue.py`
  - SHA-256 `d91ccf660daca6025e52609018d6975da03282e0cb0830bb65a6bb16949a7d9e`
- `src/qa_agent/app/build_client_import_queue.py`
  - SHA-256 `74a874fb440e78d938c3c1e31daff12633b82c675fe7ebcb43eb40cdf799297c`
- `tests/test_client_import_queue.py`
  - SHA-256 `37f07d61c4b48cb0fb77affdc1b7b4053d86d570ef1b8bdcc131d4f9bd1b32b5`
- `ingestion/raw/client_packages/README.md`
  - SHA-256 `1dacd171d7e259f9e9ee5def90215ac69b5576bc8fed965db87d99d2351d092b`

Interpretation:
- Round36 does not decode protected LuaScripts or `.ns` payloads.
- It gives the next offline/static work a durable priority queue instead of a loose artifact list.
- The highest-priority queue items point at LuaScripts hero/skill stems, NEP2 `CGameProtector::InitLuaScriptsScan`, and the GameAssembly `xluaL_loadbuffer` / `TextAsset::get_bytes` path.

Next step:
- Continue offline/static only.
- Pick a high-priority decoder target from `nslg-client-import-queue-round36.yaml`, preferably NEP2 `CGameProtector::InitLuaScriptsScan` or the GameAssembly `xluaL_loadbuffer` / `TextAsset::get_bytes` path.
- Convert any readable domain records into reviewed staging only after manual semantic validation with stable `source_ref` / `evidence_ref`.

## 2026-05-20 NEP2 Provenance Closures Round37 / Bundle Round38 / Queue Round39

Goal slice: carry external NEP2 provenance closure results back into qa-agent as sanitized evidence, then make the latest bundle and import queue point at that evidence.

Actions:
- Read `.codex-autonomy/state.json`, `.codex-autonomy/WORKLOG.md`, project instructions, and qa-agent package instructions before acting.
- Inspected external readonly artifacts under `C:\Users\Lan\Documents\New project\threads\artifacts`.
- Added `src/qa_agent/ingestion/client_nep2_provenance.py`.
- Added CLI `src/qa_agent/app/summarize_nep2_provenance_closures.py`.
- Added tests in `tests/test_client_nep2_provenance.py`.
- Generated `ingestion/raw/client_packages/nslg-nep2-provenance-closures-round37.yaml` from external provenance closure rounds 137-158.
- Updated `src/qa_agent/ingestion/client_evidence_bundle.py` and `src/qa_agent/app/build_client_evidence_bundle.py` so evidence bundles include the NEP2 provenance closure batch.
- Generated `ingestion/raw/client_packages/nslg-client-evidence-bundle-round38.yaml`.
- Updated `src/qa_agent/ingestion/client_import_queue.py` to default to the round38 evidence bundle.
- Generated `ingestion/raw/client_packages/nslg-client-import-queue-round39.yaml`.
- Updated `ingestion/raw/client_packages/README.md` with the new artifacts and rebuild commands.

Result:
- NEP2 provenance closure schema: `nslg.nep2_provenance_closure_batch.v1`.
- Source id: `nep2-provenance-closures-round37`.
- External closure rounds summarized: 137-158.
- Closed NEP2 RVA leads: 22.
- Closure status counts:
  - `closed_no_file_buffer_provenance`: 22.
- Pointer-ref classification counts:
  - `internal_rdata_tables_no_asset_owner`: 17.
  - `none`: 5.
- Target verdict counts:
  - `nontrivial helper but no file/CAB provenance`: 12.
  - `metadata/control helper; no current CAB transform proof`: 10.
- Next unclosed shape lead from the external analysis log: `0x4a471a`.
- Round38 evidence bundle:
  - Artifact count: 6.
  - Evidence ref count: 339.
  - `safe_for_publish=false`.
  - `normalized_staging_entries=63`.
- Round39 import queue:
  - Queue item count: 87.
  - `decoded_hero_review`: 63.
  - `luascripts_decoder_target`: 16.
  - `lua_crypto_decoder_target`: 4.
  - `nep2_static_trace_target`: 4.

Verification:
- Targeted client ingestion tests passed:
  - `PYTHONPATH=src python3 -m unittest tests.test_client_nep2_provenance tests.test_client_evidence_bundle tests.test_client_import_queue tests.test_client_package_scan tests.test_client_decoded tests.test_client_luascripts tests.test_client_nep2_luascripts tests.test_client_lua_crypto -v`
  - 21 tests passed.
- Full qa-agent tests passed:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v`
  - 195 tests passed.
- Sanitization check passed:
  - `rg -n -e "C:" -e "/mnt/" -e "/home/" -e "/Users/" -e "server_id" -e "role_id" -e "mail" -e "chat" ingestion/raw/client_packages/nslg-nep2-provenance-closures-round37.yaml ingestion/raw/client_packages/nslg-client-evidence-bundle-round38.yaml ingestion/raw/client_packages/nslg-client-import-queue-round39.yaml`
  - No matches.

Hashes:
- `ingestion/raw/client_packages/nslg-nep2-provenance-closures-round37.yaml`
  - SHA-256 `e3ee8b58b8982e1121648ee1c506839f05054e955e4c981fe0e99747eeb6df93`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round38.yaml`
  - SHA-256 `7da7ab7a06eb4cb62f13bee16921c56c9324d8630a718ee2eb38314fbbef2b2a`
- `ingestion/raw/client_packages/nslg-client-import-queue-round39.yaml`
  - SHA-256 `0e517386b3b821ff439930cdddef86c56fe42618ee5f88d417481bdb2a115673`
- `src/qa_agent/ingestion/client_nep2_provenance.py`
  - SHA-256 `13cff91e916297d7b2a32590e320e3595d3da6003428eb8213c04f18b5891332`
- `src/qa_agent/app/summarize_nep2_provenance_closures.py`
  - SHA-256 `60ed791839c4abc98caa75e50ae12a2519a44c39d293755e1c9022d3e754b913`
- `tests/test_client_nep2_provenance.py`
  - SHA-256 `dfdbb34fce594773e32b24286836256b59c1cd7ebac6f4588960ce2c1f1334f4`

Interpretation:
- This slice does not decode protected LuaScripts or `.ns` payloads.
- It does make the negative NEP2 search evidence durable in qa-agent, closing 22 shape-only leads so later work does not repeat broad vector/table-loop scans.
- The latest bundle now includes both positive decoder targets and negative route-closure evidence.
- The next candidate named by the external analysis log is NEP2 `0x4a471a`, but the state now explicitly gates future NEP2 work on caller/callee provenance, keyword/import ownership, or file-buffer/asset owner evidence.

Next step:
- Continue offline/static only.
- Either inspect NEP2 `0x4a471a` with the stricter provenance gate or pivot to GameAssembly `xluaL_loadbuffer` / `TextAsset::get_bytes` and protected `global-metadata.dat` correlation.

## 2026-05-20 External Round159 Closure / NEP2 Provenance Round40 / Bundle Round41 / Queue Round42

Goal slice: close the external NEP2 `0x4a471a` candidate as negative evidence, then refresh qa-agent's provenance closure batch, evidence bundle, and import queue to point at the latest offline/static findings.

Actions:
- Read `.codex-autonomy/state.json`, `.codex-autonomy/WORKLOG.md`, project instructions, and qa-agent package instructions before acting.
- Created external readonly closure script `threads/artifacts/round159_nep2_4a471a_provenance_closure.py`.
- Generated external artifacts:
  - `threads/artifacts/nep2_4a471a_provenance_closure_round159.json`
  - `threads/artifacts/nep2_4a471a_provenance_closure_round159.md`
  - `threads/artifacts/nep2_4a471a_provenance_closure_round159.asm`
- Updated external reverse-analysis state and analysis thread to record Round159.
- Updated `src/qa_agent/ingestion/client_nep2_provenance.py` so the parser accepts both `next highest` and `next unclosed` analysis-log wording.
- Updated tests for the new next-target parsing behavior.
- Regenerated `ingestion/raw/client_packages/nslg-nep2-provenance-closures-round40.yaml`.
- Regenerated `ingestion/raw/client_packages/nslg-client-evidence-bundle-round41.yaml`.
- Regenerated `ingestion/raw/client_packages/nslg-client-import-queue-round42.yaml`.
- Updated `ingestion/raw/client_packages/README.md` to list round40/41/42 artifacts and rebuild commands.

Result:
- External Round159 target: NEP2 `0x4a471a-0x4a6345`, size `0x1c2b`.
- Round159 direct callers: 0.
- Round159 direct callees: 0.
- Round159 nonexec pointer refs: 6.
- Round159 pointer ref classification: `internal_rdata_tables_no_asset_owner`.
- Round159 pointer owner signal count: 0.
- Round159 strong provenance found: false.
- Round159 verdict: close `0x4a471a` as shape-only / data-table false lead with no file-buffer, CAB, SerializedFile, global-metadata, AssetBundle, LuaScripts payload, keyword/import, or asset owner path.
- Round40 NEP2 provenance closure batch:
  - Artifact count: 23.
  - Round range: 137-159.
  - `closed_no_file_buffer_provenance`: 23.
  - Next unclosed shape lead: `0x4a28e9`.
  - `safe_for_publish=false`.
  - `publishable_knowledge_entries=0`.
- Round41 evidence bundle:
  - Artifact count: 6.
  - Evidence ref count: 340.
  - `safe_for_publish=false`.
  - `normalized_staging_entries=63`.
- Round42 import queue:
  - Queue item count: 87.
  - `decoded_hero_review`: 63.
  - `luascripts_decoder_target`: 16.
  - `lua_crypto_decoder_target`: 4.
  - `nep2_static_trace_target`: 4.
  - `blocked_pending_decoder`: 20.
  - `needs_manual_review`: 63.
  - `static_trace_target`: 4.
  - `safe_for_publish=false`.
  - `auto_publish_allowed=false`.

Verification:
- External Round159 script validation passed:
  - `python -m py_compile threads/artifacts/round137_nep2_620670_provenance_closure.py threads/artifacts/round159_nep2_4a471a_provenance_closure.py`
  - `python threads/artifacts/round159_nep2_4a471a_provenance_closure.py`
  - `python -m json.tool threads/artifacts/nep2_4a471a_provenance_closure_round159.json`
- Targeted client ingestion tests passed:
  - `PYTHONPATH=src python3 -m unittest tests.test_client_nep2_provenance tests.test_client_evidence_bundle tests.test_client_import_queue tests.test_client_package_scan tests.test_client_decoded tests.test_client_luascripts tests.test_client_nep2_luascripts tests.test_client_lua_crypto -v`
  - 21 tests passed.
- Full qa-agent tests passed:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v`
  - 195 tests passed.
- Sanitization check passed:
  - `rg -n -e "C:" -e "/mnt/" -e "/home/" -e "/Users/" -e "server_id" -e "role_id" -e "mail" -e "chat" ingestion/raw/client_packages/nslg-nep2-provenance-closures-round40.yaml ingestion/raw/client_packages/nslg-client-evidence-bundle-round41.yaml ingestion/raw/client_packages/nslg-client-import-queue-round42.yaml`
  - No matches.

Hashes:
- `ingestion/raw/client_packages/nslg-nep2-provenance-closures-round40.yaml`
  - SHA-256 `dda7c8510586cac8cb36750bdcc265ecd06fafc8b4eabf50a419252622b5ac01`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round41.yaml`
  - SHA-256 `42b2e8e7d1b5e4115447d44169b56195798e188718313b886df8608be3f3d90a`
- `ingestion/raw/client_packages/nslg-client-import-queue-round42.yaml`
  - SHA-256 `c79e4f169eb78fd497327beb649bf41376b349efe8ce4bc56f0a8a0a71993681`
- `src/qa_agent/ingestion/client_nep2_provenance.py`
  - SHA-256 `67ae3030fee8475f0b8d3685b3d31bac2d0ff6081f24f325714b1960251ec314`
- `tests/test_client_nep2_provenance.py`
  - SHA-256 `aa1f43a3ac3f52920ac5b416e5c634f7db7f8f37a83a20674816f329d903ea15`
- `src/qa_agent/ingestion/client_evidence_bundle.py`
  - SHA-256 `e84bb7e2faf1dac803aa31c0d66c31a413278110a5b14f0d34e76eac26f22660`
- `tests/test_client_evidence_bundle.py`
  - SHA-256 `ab62e39c6725a28b77fa463d804557a8533021ba609971b0dfd709e83bcba8c2`
- `src/qa_agent/ingestion/client_import_queue.py`
  - SHA-256 `715414c06ec82686399fe104291485df3ffc788ed831d39dd06958ccd5343ef9`
- `tests/test_client_import_queue.py`
  - SHA-256 `b9846125a7b9351fd21160e01a51ee3a597da3831f86986a015abdc8cc25cb97`
- `ingestion/raw/client_packages/README.md`
  - SHA-256 `e7acceea5cbd7cda94a65ab6262e7451deca45cc847d35eabf2777736458eea6`

Interpretation:
- This slice still does not decode protected LuaScripts or `.ns` payloads.
- It closes one more NEP2 shape-only lead and keeps negative search evidence durable in qa-agent.
- The latest qa-agent bundle now points at round40 provenance evidence, and the latest import queue points at round41 bundle evidence.
- Future NEP2 work should not continue broad shape-only scanning unless there is caller/callee provenance, keyword/import ownership, or file-buffer/asset owner evidence.

Next step:
- Continue offline/static only.
- Use NEP2 `0x4a28e9` only under the strict provenance gate; otherwise pivot to GameAssembly `xluaL_loadbuffer` / `TextAsset::get_bytes` and protected `global-metadata.dat` correlation.

## 2026-05-20 GameAssembly Route Trace Round43 / Bundle Round44 / Queue Round45

Goal slice: pivot from broad NEP2 shape-only closure to GameAssembly route evidence, then carry the new static TextAsset/loadbuffer correlation evidence into qa-agent as sanitized decoder planning material.

Actions:
- Read `.codex-autonomy/state.json`, `.codex-autonomy/WORKLOG.md`, project instructions, and qa-agent package instructions before acting.
- Added external script `threads/artifacts/round160_gameassembly_textasset_loadbuffer_correlation.py`.
- Generated external Round160 artifacts:
  - `threads/artifacts/gameassembly_textasset_loadbuffer_correlation_round160.json`
  - `threads/artifacts/gameassembly_textasset_loadbuffer_correlation_round160.md`
  - `threads/artifacts/gameassembly_textasset_loadbuffer_correlation_round160.asm`
- Added `src/qa_agent/ingestion/client_gameassembly_trace.py`.
- Added CLI `src/qa_agent/app/summarize_gameassembly_route_trace.py`.
- Added tests in `tests/test_client_gameassembly_trace.py`.
- Updated client evidence bundle and import queue builders to include GameAssembly route trace evidence.
- Generated `ingestion/raw/client_packages/nslg-gameassembly-route-trace-round43.yaml`.
- Generated `ingestion/raw/client_packages/nslg-client-evidence-bundle-round44.yaml`.
- Generated `ingestion/raw/client_packages/nslg-client-import-queue-round45.yaml`.
- Updated `ingestion/raw/client_packages/README.md` with the new current artifacts and rebuild commands.

Result:
- External Round160:
  - Target strings found: 9.
  - Code refs to target strings: 0.
  - Functions with target string refs: 0.
  - Route-signal functions needing review: 0.
  - Static string inventory includes `UnityEngine.TextAsset::get_bytes()`, TextAsset data helpers, AssetBundle memory APIs, and `xluaL_loadbuffer`.
  - No static `TextAsset::get_bytes` -> `xluaL_loadbuffer` bridge was proven.
- Round43 GameAssembly route trace:
  - Artifact count: 6.
  - Round range: 42-160.
  - Status counts: 3 `static_trace_seed`, 3 `negative_route_correlation`.
  - Route signal records: 0.
  - Total target strings: 270.
  - Total code refs: 15.
  - Total function refs: 31.
  - `safe_for_publish=false`.
- Round44 evidence bundle:
  - Artifact count: 7.
  - Evidence ref count: 346.
  - `safe_for_publish=false`.
  - `normalized_staging_entries=63`.
  - Decoder target artifacts: LuaScripts catalog, LuaScripts crypto evidence, NEP2 static evidence, GameAssembly route trace.
- Round45 import queue:
  - Queue item count: 88.
  - `decoded_hero_review`: 63.
  - `luascripts_decoder_target`: 16.
  - `lua_crypto_decoder_target`: 4.
  - `nep2_static_trace_target`: 4.
  - `gameassembly_static_trace_target`: 1.
  - `blocked_pending_decoder`: 20.
  - `needs_manual_review`: 63.
  - `static_trace_target`: 5.
  - `safe_for_publish=false`.
  - `auto_publish_allowed=false`.

Verification:
- External Round160 validation passed:
  - `python -m py_compile threads\artifacts\round160_gameassembly_textasset_loadbuffer_correlation.py`
  - `python threads\artifacts\round160_gameassembly_textasset_loadbuffer_correlation.py`
  - `python -m json.tool threads\artifacts\gameassembly_textasset_loadbuffer_correlation_round160.json`
- Targeted client ingestion tests passed:
  - `PYTHONPATH=src python3 -m unittest tests.test_client_gameassembly_trace tests.test_client_evidence_bundle tests.test_client_import_queue tests.test_client_nep2_provenance tests.test_client_package_scan tests.test_client_decoded tests.test_client_luascripts tests.test_client_nep2_luascripts tests.test_client_lua_crypto -v`
  - 23 tests passed.
- Full qa-agent tests passed:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v`
  - 197 tests passed.
- Sanitization check passed:
  - `rg -n -e "C:" -e "/mnt/" -e "/home/" -e "/Users/" -e "server_id" -e "role_id" -e "mail" -e "chat" ingestion/raw/client_packages/nslg-gameassembly-route-trace-round43.yaml ingestion/raw/client_packages/nslg-client-evidence-bundle-round44.yaml ingestion/raw/client_packages/nslg-client-import-queue-round45.yaml`
  - No matches.

Hashes:
- `ingestion/raw/client_packages/nslg-gameassembly-route-trace-round43.yaml`
  - SHA-256 `b1444ccbfdaae2c8a79235aa0d0ccc1e392654284b330c9e0bf0eced50688199`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round44.yaml`
  - SHA-256 `5833d4dac33cc805a0f7bdeeb3b254541a601bd922d9da98ab233fb3cc0e44fe`
- `ingestion/raw/client_packages/nslg-client-import-queue-round45.yaml`
  - SHA-256 `37a05f3a8ca024ad735b8975f6c25df1643eba40196bb7285abfb4278cffeeb7`
- `src/qa_agent/ingestion/client_gameassembly_trace.py`
  - SHA-256 `e62c71ee72aaeb28a13e4920ac20a068b56ed1d3146bf0062d9ffb8c479a2e95`
- `src/qa_agent/app/summarize_gameassembly_route_trace.py`
  - SHA-256 `1ec40b1b5269b012733a317e6276cf78fa3a4885686609c77f3fc90bb5f240a5`
- `tests/test_client_gameassembly_trace.py`
  - SHA-256 `738640df3754fcd6ed319abbe5cbc0d4b86a87eda6570c08f89d9a3189700f75`
- `src/qa_agent/ingestion/client_evidence_bundle.py`
  - SHA-256 `d7a01cb63a537e661c204ca71330874af3f2963b8511d4738d07aef857998841`
- `src/qa_agent/ingestion/client_import_queue.py`
  - SHA-256 `ad052683985512a60c692cad46db38e5c6b71c3c476bd9d7f89130a51fa59cae`
- `ingestion/raw/client_packages/README.md`
  - SHA-256 `830ed8994c6db629af543cd968a7fee0edd56d759357d60a777ec5166d89e0fd`

Interpretation:
- This slice still does not decode protected LuaScripts or `.ns` payloads.
- It makes the GameAssembly route evidence durable in qa-agent and prevents repeating broad `TextAsset::get_bytes` / `xluaL_loadbuffer` string chasing.
- The best next work is no longer broad GameAssembly string search; it is NEP2 `InitLuaScriptsScan` or runtime-independent TextAsset/LuaScripts payload decoder recovery.

Next step:
- Continue offline/static only.
- Prioritize NEP2 `InitLuaScriptsScan` or a runtime-independent TextAsset/LuaScripts payload decoder recovery path.
- Inspect NEP2 `0x4a28e9` only if strict caller/callee provenance, keyword/import ownership, or file-buffer/asset-owner evidence exists.

## 2026-05-20T22:48:01+08:00 - NEP2 InitLuaScriptsScan bridge evidence import

Slice:
- Materialized external Round161 NEP2 `InitLuaScriptsScan` bridge summary into qa-agent evidence tracking.
- Kept the artifact as decoder-routing evidence only; no publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_nep2_bridge.py`.
- Added `src/qa_agent/app/summarize_nep2_init_bridge.py`.
- Added `tests/test_client_nep2_bridge.py`.
- Extended client evidence bundle and import queue builders to include `nep2_init_luascripts_bridge`.
- Updated `ingestion/raw/client_packages/README.md` with round46/47/48 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-nep2-init-bridge-round46.yaml`
  - Bridge records: `4`.
  - Candidate functions: `13`.
  - Candidate with file import: `1`.
  - Candidate with keyword xref: `0`.
  - Candidate crypto-like: `0`.
  - `decryptor_body_proven=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round47.yaml`
  - Artifact count: `8`.
  - Evidence refs: `367`.
  - Decoder target artifacts now include `nep2_init_luascripts_bridge`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round48.yaml`
  - Queue item count: `89`.
  - Added `nep2_init_bridge_trace_target=1`.
  - Static trace targets: `6`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_nep2_bridge.py src/qa_agent/app/summarize_nep2_init_bridge.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_nep2_bridge tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 199 tests.
- Sensitive path/marker scan on round46/47/48 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-nep2-init-bridge-round46.yaml`
  - SHA-256 `907708d4ea8eb98b2e3ae393be500c3e0b407fa2c7661417bab5e14d51142333`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round47.yaml`
  - SHA-256 `4239cebeaccd4ecb2f010b568d9d1a330886a35250a697b48581bd1970fe8b85`
- `ingestion/raw/client_packages/nslg-client-import-queue-round48.yaml`
  - SHA-256 `0e0bd5d3ee990b6fc8c2f10b4a348fa8b67abe7cd0e4c0eb47cf49736516cec2`

Next step:
- Continue offline/static only.
- Avoid broad string chasing and shape-only NEP2 promotion.
- Prioritize runtime-independent TextAsset/LuaScripts payload decoder recovery, or trace InitLuaScriptsScan caller/owner only when strict file-buffer, asset-owner, keyword/import, or mutation provenance exists.

## 2026-05-20T23:01:31+08:00 - LuaScripts payload cipher profile import

Slice:
- Materialized external Round162 LuaScripts payload cipher-profile evidence into qa-agent evidence tracking.
- Kept the artifact as decoder-routing evidence only; no publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_payload_cipher_profile.py`.
- Added `src/qa_agent/app/summarize_luascripts_payload_cipher_profile.py`.
- Added `tests/test_client_payload_cipher_profile.py`.
- Extended client evidence bundle and import queue builders to include `luascripts_payload_cipher_profile`.
- Updated `ingestion/raw/client_packages/README.md` with round49/50/51 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-luascripts-payload-cipher-profile-round49.yaml`
  - Payload profiles: `16`.
  - Payload status: `16` `high_entropy_16byte_aligned`.
  - Cross-file shared 16-byte blocks: `0`.
  - Duplicate first blocks: `0`.
  - Single-byte XOR plaintext-like candidates: `0`.
  - Crib-derived XOR plaintext-like candidates: `0`.
  - `lua_payload_decoder_recovered=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round50.yaml`
  - Artifact count: `9`.
  - Evidence refs: `383`.
  - Decoder target artifacts now include `luascripts_payload_cipher_profile`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round51.yaml`
  - Queue item count: `90`.
  - Added `luascripts_payload_cipher_profile_target=1`.
  - Blocked pending decoder items: `21`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_payload_cipher_profile.py src/qa_agent/app/summarize_luascripts_payload_cipher_profile.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_payload_cipher_profile tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 201 tests.
- Sensitive path/marker scan on round49/50/51 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-luascripts-payload-cipher-profile-round49.yaml`
  - SHA-256 `0c88e6b4abf6c1bd1954be35fa1f12a8bf03d4130a2224fbebbabdcfe3abba31`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round50.yaml`
  - SHA-256 `761f21660afd331ec700c9e59bfcb4004dbdef0ae4d0e9bbc1219e997900a45c`
- `ingestion/raw/client_packages/nslg-client-import-queue-round51.yaml`
  - SHA-256 `5f30c3bdb3144c7099d0641d724422748f5900df7c2af79157c4e476ececead9`

Next step:
- Continue offline/static only.
- Prioritize native buffer-owner tracing at the `TextAsset bytes -> decoder -> xLua loadbuffer` boundary.
- Do not spend another broad round on static key/string brute force unless new file-buffer, asset-owner, keyword/import, or mutation provenance appears.

## 2026-05-20T23:55:00+08:00 - Native loadbuffer boundary trace import

Slice:
- Materialized external Round163 native loadbuffer boundary trace into qa-agent evidence tracking.
- Kept the artifact as decoder-routing evidence only; no publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_native_boundary_trace.py`.
- Added `src/qa_agent/app/summarize_native_loadbuffer_boundary.py`.
- Added `tests/test_client_native_boundary_trace.py`.
- Extended client evidence bundle and import queue builders to include `native_loadbuffer_boundary_trace`.
- Updated `ingestion/raw/client_packages/README.md` with round52/53/54 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-native-loadbuffer-boundary-round52.yaml`
  - Round: `163`.
  - Module count: `4`.
  - Loadbuffer export signals: `3`.
  - Boundary import calls: `224`.
  - Candidate function signals: `1`.
  - `gameassembly_static_xlua_import_present=false`.
  - `textasset_to_loadbuffer_owner_proven=false`.
  - `lua_payload_decoder_recovered=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round53.yaml`
  - Artifact count: `10`.
  - Evidence refs: `387`.
  - Decoder target artifacts now include `native_loadbuffer_boundary_trace`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round54.yaml`
  - Queue item count: `91`.
  - Added `native_loadbuffer_boundary_trace_target=1`.
  - Static trace targets: `7`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_native_boundary_trace.py src/qa_agent/app/summarize_native_loadbuffer_boundary.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_native_boundary_trace tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 203 tests.
- Sensitive path/marker scan on round52/53/54 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-native-loadbuffer-boundary-round52.yaml`
  - SHA-256 `3198df38465043f02261122e9ad3da6dae3f8d307e4c9fcdc945c582afb8d2b2`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round53.yaml`
  - SHA-256 `31eaeea5e690170faea0026146f58e1af4471d06b213195ac49d270b7a90cb3f`
- `ingestion/raw/client_packages/nslg-client-import-queue-round54.yaml`
  - SHA-256 `1ec683d255b1a4fa40787ab531488e616dfff8d6a6635031f540010c0c583292`

Next step:
- Continue offline/static only.
- Prioritize runtime registration tables or managed `RuntimeInitializeOnLoad` metadata for `NSLGame.Patcher.GameUpdater.InitLuaEnv`.
- Use protected/global-metadata recovery to identify method ownership for `TextAsset` bytes and Lua env initialization.
- Do not promote broad import/export or shape-only hits unless they prove file-buffer, asset-owner, or payload-buffer ownership.

## 2026-05-21T00:20:00+08:00 - Runtime init metadata route import

Slice:
- Materialized external Round164 runtime init / protected metadata route evidence into qa-agent evidence tracking.
- Kept the artifact as decoder-planning evidence only; no publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_runtime_init_route.py`.
- Added `src/qa_agent/app/summarize_runtime_init_metadata_route.py`.
- Added `tests/test_client_runtime_init_route.py`.
- Extended client evidence bundle and import queue builders to include `runtime_init_metadata_route`.
- Updated `ingestion/raw/client_packages/README.md` with round55/56/57 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-runtime-init-metadata-route-round55.yaml`
  - Round: `164`.
  - Runtime InitLuaEnv anchor known: `true`.
  - Standalone RuntimeInitializeOnLoads file present in current snapshot: `false`.
  - global-metadata protected wrapper confirmed: `true`.
  - global-metadata file size: `21182776`.
  - global-metadata plaintext needle hits: `0`.
  - global-metadata duplicate 16-byte block kinds: `20744`.
  - `init_lua_env_method_address_recovered=false`.
  - `lua_payload_decoder_recovered=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round56.yaml`
  - Artifact count: `11`.
  - Evidence refs: `392`.
  - Decoder target artifacts now include `runtime_init_metadata_route`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round57.yaml`
  - Queue item count: `92`.
  - Added `runtime_init_metadata_route_target=1`.
  - Static trace targets: `8`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_runtime_init_route.py src/qa_agent/app/summarize_runtime_init_metadata_route.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_runtime_init_route tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 205 tests.
- Sensitive path/marker scan on round55/56/57 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-runtime-init-metadata-route-round55.yaml`
  - SHA-256 `6bfa279fcb20f40ab5d55f0ff25dad6a796afd8b10e9404c2fb33fa635f99819`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round56.yaml`
  - SHA-256 `0f6e7d4c0f678c16b146973fcec8f1a26dc58c108250f979437548f24807a9fd`
- `ingestion/raw/client_packages/nslg-client-import-queue-round57.yaml`
  - SHA-256 `24ab9ec8a2ee8d1903c6fef5049232b5ee3de4e565ded5943d64073739272526`

Next step:
- Continue offline/static only.
- Recover protected `global-metadata.dat` enough to map `NSLGame.Patcher.GameUpdater.InitLuaEnv` to IL2CPP method ownership, or trace runtime registration/descriptor resolver tables around GameAssembly internal resolver candidate `0x5ccc30` without live attach.
- Do not promote broad strings/imports, runtime-init labels, or NEP2 bridge metadata without method ownership or payload-buffer provenance.

## 2026-05-20T23:46:00+08:00 - GameAssembly resolver candidate trace import

Slice:
- Materialized external Round165 GameAssembly `0x5ccc30` resolver/descriptor candidate trace into qa-agent evidence tracking.
- Kept the artifact as decoder-planning evidence only; no publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_gameassembly_resolver_trace.py`.
- Added `src/qa_agent/app/summarize_gameassembly_resolver_trace.py`.
- Added `tests/test_client_gameassembly_resolver_trace.py`.
- Extended client evidence bundle and import queue builders to include `gameassembly_resolver_candidate_trace`.
- Updated `ingestion/raw/client_packages/README.md` with round58/59/60 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-gameassembly-resolver-trace-round58.yaml`
  - Round: `165`.
  - Resolver candidate RVA: `0x5ccc30`.
  - Direct rel32 callsites: `2948`.
  - Sampled direct caller functions: `240`.
  - Caller functions with xLua/TextAsset/LuaScripts-related keyword refs: `28`.
  - `descriptor_resolver_pattern_supported=true`.
  - `candidate_has_payload_owner_signal=false`.
  - `method_ownership_recovered=false`.
  - `textasset_payload_owner_proven=false`.
  - `lua_payload_decoder_recovered=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round59.yaml`
  - Artifact count: `12`.
  - Evidence refs: `418`.
  - Decoder target artifacts now include `gameassembly_resolver_candidate_trace`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round60.yaml`
  - Queue item count: `93`.
  - Added `gameassembly_resolver_trace_target=1`.
  - Static trace targets: `9`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_gameassembly_resolver_trace.py src/qa_agent/app/summarize_gameassembly_resolver_trace.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_gameassembly_resolver_trace tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 207 tests.
- Sensitive path/marker scan on round58/59/60 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-gameassembly-resolver-trace-round58.yaml`
  - SHA-256 `a6ac8dd74f0ee6670c6f93c26dfc39e07974cc41e85caef7776a8710347eb85a`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round59.yaml`
  - SHA-256 `931374b61674274bd77c7d80a185b29b42e92ed73026d9c5c8fc78c93a48c6c2`
- `ingestion/raw/client_packages/nslg-client-import-queue-round60.yaml`
  - SHA-256 `3ae269aa2325e386d7be1ea8ad2de20f2f86398e08a34e8e705e843fbc330b3b`

Next step:
- Continue offline/static only.
- Recover protected `global-metadata.dat` enough to map `NSLGame.Patcher.GameUpdater.InitLuaEnv` to IL2CPP method ownership.
- If continuing through GameAssembly, inspect only resolver callers that also prove TextAsset/file-buffer payload ownership.
- Do not promote descriptor resolver strings or broad callsite counts as decoder evidence without method ownership or payload-buffer provenance.

## 2026-05-20T23:55:00+08:00 - GameAssembly resolver caller payload-owner trace import

Slice:
- Materialized external Round166 GameAssembly `0x5ccc30` direct-caller payload-owner trace into qa-agent evidence tracking.
- Kept the artifact as decoder-planning negative evidence only; no publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_gameassembly_resolver_caller_trace.py`.
- Added `src/qa_agent/app/summarize_gameassembly_resolver_caller_trace.py`.
- Added `tests/test_client_gameassembly_resolver_caller_trace.py`.
- Extended client evidence bundle and import queue builders to include `gameassembly_resolver_caller_payload_trace`.
- Updated `ingestion/raw/client_packages/README.md` with round61/62/63 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-gameassembly-resolver-caller-trace-round61.yaml`
  - Round: `166`.
  - Direct rel32 callsites: `2948`.
  - Unique direct caller functions inspected: `2870`.
  - xLua/lua API descriptor-only callers: `150`.
  - TextAsset caller refs: `0`.
  - LuaScripts/data-stem caller refs: `0`.
  - Payload-owner candidates: `0`.
  - `textasset_payload_owner_proven=false`.
  - `file_buffer_payload_owner_proven=false`.
  - `lua_payload_decoder_recovered=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round62.yaml`
  - Artifact count: `13`.
  - Evidence refs: `421`.
  - Decoder target artifacts now include `gameassembly_resolver_caller_payload_trace`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round63.yaml`
  - Queue item count: `94`.
  - Added `gameassembly_resolver_caller_trace_target=1`.
  - Static trace targets: `10`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_gameassembly_resolver_caller_trace.py src/qa_agent/app/summarize_gameassembly_resolver_caller_trace.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_gameassembly_resolver_caller_trace tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 209 tests.
- Sensitive path/marker scan on round61/62/63 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-gameassembly-resolver-caller-trace-round61.yaml`
  - SHA-256 `7d25cdfd5af9608a25daf4f883dfbae4304823a9d1c3043f414d9d1c1dfbd2f8`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round62.yaml`
  - SHA-256 `db33f8358b9bec2d3d9acdc2c6ece9ee71ece7971ae7534e4d5dbf059a02cd54`
- `ingestion/raw/client_packages/nslg-client-import-queue-round63.yaml`
  - SHA-256 `d0d855ffcf76288fc31e211e81dbabc48c3a40465e7f319fa1613e8fba5ea579`

Next step:
- Continue offline/static only.
- Prioritize protected `global-metadata.dat` recovery for `NSLGame.Patcher.GameUpdater.InitLuaEnv` method ownership.
- Alternatively pivot back to NEP2 `InitLuaScriptsScan` file-buffer provenance.
- Do not keep chasing GameAssembly `0x5ccc30` direct callers unless metadata recovery or a separate owner trace gives a caller TextAsset/file-buffer provenance.

## 2026-05-21T00:15:00+08:00 - Global metadata transform probe import

Slice:
- Materialized external Round167 protected `global-metadata.dat` bounded transform probe into qa-agent evidence tracking.
- Kept the artifact as negative decoder-planning evidence only; no publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_global_metadata_transform_probe.py`.
- Added `src/qa_agent/app/summarize_global_metadata_transform_probe.py`.
- Added `tests/test_client_global_metadata_transform_probe.py`.
- Extended client evidence bundle and import queue builders to include `global_metadata_transform_probe`.
- Updated `ingestion/raw/client_packages/README.md` with round64/65/66 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-global-metadata-transform-probe-round64.yaml`
  - Round: `167`.
  - Transform candidates tested: `1314`.
  - Known metadata plaintext hit candidates: `0`.
  - Best header valid pair count: `0`.
  - 16-byte repeated block duplicate kinds: `20744`.
  - Plaintext metadata recovered: `false`.
  - InitLuaEnv method ownership recovered: `false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round65.yaml`
  - Artifact count: `14`.
  - Evidence refs: `424`.
  - Decoder target artifacts now include `global_metadata_transform_probe`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round66.yaml`
  - Queue item count: `95`.
  - Added `global_metadata_transform_probe_target=1`.
  - Static trace targets: `11`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_global_metadata_transform_probe.py src/qa_agent/app/summarize_global_metadata_transform_probe.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py tests/test_client_global_metadata_transform_probe.py tests/test_client_evidence_bundle.py tests/test_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_global_metadata_transform_probe tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 211 tests.
- Sensitive path/marker scan on round64/65/66 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-global-metadata-transform-probe-round64.yaml`
  - SHA-256 `befdf9cf878c533cd18a14fd89a38cfdc358fd92a843e4a2e3ae4c4b2d2abade`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round65.yaml`
  - SHA-256 `c3d8582f8dde69f34b684db225b533e828c96ccaeb3f2c4c352fdd163d0f4f78`
- `ingestion/raw/client_packages/nslg-client-import-queue-round66.yaml`
  - SHA-256 `7d7be378f8270ab6674ebc60d8ec02fc60595294f173d30d26d3ef5e2aa2c168`

Next step:
- Continue offline/static only.
- Pivot from file-only protected metadata transforms to loader mutation provenance.
- Prioritize functions that combine file APIs, `global-metadata.dat` wrapper constants, +8 payload handling, and 16-byte loops.
- Do not promote metadata recovery unless standard IL2CPP header pairs plus readable `Assembly-CSharp` / `NSLGame` strings are recovered.

## 2026-05-21T00:29:25+08:00 - Global metadata loader-mutation scan import

Slice:
- Materialized external Round168 protected `global-metadata.dat` loader-mutation static scan into qa-agent evidence tracking.
- Kept the artifact as static trace seed / decoder-planning evidence only; no decoded metadata or publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_global_metadata_loader_scan.py`.
- Added `src/qa_agent/app/summarize_global_metadata_loader_scan.py`.
- Added `tests/test_client_global_metadata_loader_scan.py`.
- Extended client evidence bundle and import queue builders to include `global_metadata_loader_mutation_scan`.
- Updated `ingestion/raw/client_packages/README.md` with round67/68/69 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-global-metadata-loader-scan-round67.yaml`
  - External round: `168`.
  - Binaries scanned: `4`.
  - Function candidates scored: `554`.
  - Full loader-mutation gate candidates: `0`.
  - File API + 16-byte/loop candidates: `2`.
  - Metadata reference candidates: `0`.
  - Plaintext metadata recovered: `false`.
  - InitLuaEnv method ownership recovered: `false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round68.yaml`
  - Artifact count: `15`.
  - Evidence refs: `427`.
  - Decoder target artifacts now include `global_metadata_loader_mutation_scan`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round69.yaml`
  - Queue item count: `96`.
  - Added `global_metadata_loader_scan_target=1`.
  - Static trace targets: `12`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_global_metadata_loader_scan.py src/qa_agent/app/summarize_global_metadata_loader_scan.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py tests/test_client_global_metadata_loader_scan.py tests/test_client_evidence_bundle.py tests/test_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_global_metadata_loader_scan tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 213 tests.
- Sensitive path/marker scan on round67/68/69 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-global-metadata-loader-scan-round67.yaml`
  - SHA-256 `b5f8786e464b8b10938723c828ef8c8a06020c12d1da60f626e7949fc1872274`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round68.yaml`
  - SHA-256 `e2c397a1d4ca7c9210d750a070677212aafe1272f55fbfdf5fb7eee0151d2aff`
- `ingestion/raw/client_packages/nslg-client-import-queue-round69.yaml`
  - SHA-256 `04ec0d3d72762220049a63d36fad5a92f754adb1e66d7717b19351be0832be7c`

Next step:
- Continue offline/static only.
- Deep-slice `NEP2.dll 0xd410` and `0xd870` for `global-metadata.dat` path construction, `ReadFile` / `MapViewOfFile` buffer ownership, and +8 payload pointer handoff.
- Do not promote metadata recovery until standard IL2CPP header pairs plus readable `Assembly-CSharp` / `NSLGame` strings are recovered.

## 2026-05-21T00:42:05+08:00 - NEP2 metadata-loader deep-slice import

Slice:
- Materialized external Round169 NEP2 `0xd410` / `0xd870` global-metadata loader candidate deep-slice into qa-agent evidence tracking.
- Kept the artifact as negative route-closure evidence only; no decoded metadata or publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_nep2_metadata_loader_deep_slice.py`.
- Added `src/qa_agent/app/summarize_nep2_metadata_loader_deep_slice.py`.
- Added `tests/test_client_nep2_metadata_loader_deep_slice.py`.
- Extended client evidence bundle and import queue builders to include `nep2_global_metadata_loader_deep_slice`.
- Updated `ingestion/raw/client_packages/README.md` with round70/71/72 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-nep2-global-metadata-loader-deep-slice-round70.yaml`
  - External round: `169`.
  - Targets inspected: `2`.
  - Closed target count: `2`.
  - Read/mapping target count: `0`.
  - Metadata ref target count: `0`.
  - Directory walker target count: `1`.
  - File-status helper target count: `1`.
  - Plaintext metadata recovered: `false`.
  - InitLuaEnv method ownership recovered: `false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round71.yaml`
  - Artifact count: `16`.
  - Evidence refs: `430`.
  - Decoder target artifacts remain blocked; the NEP2 deep-slice artifact is a negative route closure, not a decoder target.
- `ingestion/raw/client_packages/nslg-client-import-queue-round72.yaml`
  - Queue item count: `96`.
  - Superseded `global_metadata_loader_scan_target`; added `nep2_metadata_loader_deep_slice_target=1`.
  - Static trace targets: `12`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_nep2_metadata_loader_deep_slice.py src/qa_agent/app/summarize_nep2_metadata_loader_deep_slice.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py tests/test_client_nep2_metadata_loader_deep_slice.py tests/test_client_evidence_bundle.py tests/test_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_nep2_metadata_loader_deep_slice tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 215 tests.
- Sensitive path/marker scan on round70/71/72 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-nep2-global-metadata-loader-deep-slice-round70.yaml`
  - SHA-256 `6ec4ed76f7f19be5f394f3eef1a9e65241be549a9a247bf676c5b7bae6915156`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round71.yaml`
  - SHA-256 `8e20504132e7788276ec0209bc58a76319f25c1719e738b2c0cedc0359ad399f`
- `ingestion/raw/client_packages/nslg-client-import-queue-round72.yaml`
  - SHA-256 `eaaa15bd6bc14011850d07cc0a0b1b29212a176fd57b97c9dca61fd25ca56393`

Next step:
- Continue offline/static only.
- Run a focused NEP2 actual read/mapping owner scan over `ReadFile`, `MapViewOfFile`, `CreateFileMapping`, and `GetFileSize` / `GetFileSizeEx` import owners.
- Require caller/callee provenance to `global-metadata.dat`, `LuaScripts`, `InitLuaScriptsScan`, or protected payload buffers before promoting any loader route.

## 2026-05-21T12:25:00+08:00 - NEP2 read/mapping owner scan import

Slice:
- Materialized external Round170 NEP2 actual read/mapping import-owner scan into qa-agent evidence tracking.
- Kept the artifact as negative route-closure evidence only; no decoded metadata or publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_nep2_read_mapping_owner_scan.py`.
- Added `src/qa_agent/app/summarize_nep2_read_mapping_owner_scan.py`.
- Added `tests/test_client_nep2_read_mapping_owner_scan.py`.
- Extended client evidence bundle and import queue builders to include `nep2_read_mapping_owner_scan`.
- Updated `ingestion/raw/client_packages/README.md` with round73/74/75 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-nep2-read-mapping-owner-scan-round73.yaml`
  - External round: `170`.
  - Read/mapping owner count: `2`.
  - ReadFile owner count: `0`.
  - MapViewOfFile owner count: `0`.
  - CreateFileMapping owner count: `0`.
  - GetFileSize / GetFileSizeEx owner count: `2`.
  - Metadata provenance owner count: `0`.
  - LuaScripts provenance owner count: `0`.
  - Protected payload signal owner count: `0`.
  - Provenance-linked owner count: `0`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round74.yaml`
  - Artifact count: `17`.
  - Evidence refs: `433`.
  - Decoder target artifacts unchanged; the NEP2 read/mapping owner scan artifact is a negative route closure, not a decoder target.
- `ingestion/raw/client_packages/nslg-client-import-queue-round75.yaml`
  - Queue item count: `96`.
  - Superseded `nep2_metadata_loader_deep_slice_target`; added `nep2_read_mapping_owner_scan_target=1`.
  - Static trace targets: `12`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_nep2_read_mapping_owner_scan.py src/qa_agent/app/summarize_nep2_read_mapping_owner_scan.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py tests/test_client_nep2_read_mapping_owner_scan.py tests/test_client_evidence_bundle.py tests/test_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_nep2_read_mapping_owner_scan tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 217 tests.
- Sensitive path/account-id scan on round73/74/75 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-nep2-read-mapping-owner-scan-round73.yaml`
  - SHA-256 `c1ecffd42b0b1017c0e8c81ed6312554912f69e2cea21f07d900ed04f83a98ce`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round74.yaml`
  - SHA-256 `dd83f9c4eb507415e724362c9c43a33a2f24b94816633c7874c73b4b1cd6f1fc`
- `ingestion/raw/client_packages/nslg-client-import-queue-round75.yaml`
  - SHA-256 `2ad8fd0fedacc3c80f634c95e10e840e37f00921f07ed8ba86b0a7587d7a72cb`

Next step:
- Continue offline/static only.
- Pivot from generic NEP2 file IO to InitLuaScriptsScan / CGameProtector data-reference ownership.
- Trace data records, code pointers, and consumers around InitLuaScriptsScan / CGameProtector, requiring payload-buffer provenance before promoting a loader or decoder route.
## 2026-05-21T12:41:08+08:00 - NEP2 InitLuaScriptsScan data-owner scan import

Slice:
- Materialized external Round171 NEP2 InitLuaScriptsScan / CGameProtector data-reference owner scan into qa-agent evidence tracking.
- Kept the artifact as decoder-planning route evidence only; no decoded metadata or publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_nep2_init_data_owner_scan.py`.
- Added `src/qa_agent/app/summarize_nep2_init_data_owner_scan.py`.
- Added `tests/test_client_nep2_init_data_owner_scan.py`.
- Extended client evidence bundle and import queue builders to include `nep2_init_data_owner_scan`.
- Updated `ingestion/raw/client_packages/README.md` with round76/77/78 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-nep2-init-data-owner-scan-round76.yaml`
  - External round: `171`.
  - Focus targets: `90`.
  - Data references: `255`.
  - Bridge record windows: `4`.
  - Bridge records with code pointers: `2`.
  - Inspected functions: `13`.
  - Payload-owner candidates: `0`.
  - `file_buffer_owner_proven=false`.
  - `lua_payload_decoder_recovered=false`.
  - `global_metadata_loader_proven=false`.
  - `plaintext_metadata_recovered=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round77.yaml`
  - Artifact count: `18`.
  - Evidence refs: `447`.
  - Decoder target artifacts unchanged; the InitLuaScriptsScan data-owner scan is route evidence, not a decoder proof.
- `ingestion/raw/client_packages/nslg-client-import-queue-round78.yaml`
  - Queue item count: `96`.
  - Superseded `nep2_read_mapping_owner_scan_target`; added `nep2_init_data_owner_scan_target=1`.
  - Static trace targets: `12`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_nep2_init_data_owner_scan.py src/qa_agent/app/summarize_nep2_init_data_owner_scan.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py tests/test_client_nep2_init_data_owner_scan.py tests/test_client_evidence_bundle.py tests/test_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_nep2_init_data_owner_scan tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 219 tests.
- Sensitive path/account-id scan on round76/77/78 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-nep2-init-data-owner-scan-round76.yaml`
  - SHA-256 `17b2b65f789e1d337d5019948d00fcc870562ef70df13d082a99aba547688d9a`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round77.yaml`
  - SHA-256 `741b06b7cc750a33293e8805988e24107e2f9981700d4e0b4950ae0cdde127c3`
- `ingestion/raw/client_packages/nslg-client-import-queue-round78.yaml`
  - SHA-256 `b3c1ffaab6e0408e4cb6337ae24a16cccb0094611a689c71a0bf4de6d693dbfb`

Next step:
- Continue offline/static only.
- Inspect `0x6033f0` / `0x603670` only if payload-buffer provenance can be attached.
- Otherwise prioritize TextAsset/LuaScripts payload decoder recovery from payload shape and xLua/native boundary evidence.

## 2026-05-21T12:55:00+08:00 - LuaScripts payload variant corpus import

Slice:
- Materialized external Round172 LuaScripts payload variant corpus probe into qa-agent evidence tracking.
- Kept the artifact as decoder-planning/eval evidence only; no decoded LuaScripts payload or publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_luascripts_variant_corpus.py`.
- Added `src/qa_agent/app/summarize_luascripts_payload_variant_corpus.py`.
- Added `tests/test_client_luascripts_variant_corpus.py`.
- Extended client evidence bundle and import queue builders to include `luascripts_payload_variant_corpus`.
- Updated `ingestion/raw/client_packages/README.md` with round79/80/81 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-luascripts-payload-variant-corpus-round79.yaml`
  - External round: `172`.
  - Relevant records: `104`.
  - Payload variants: `932`.
  - Stems: `16`.
  - Scenarios: `23`.
  - Unique ciphertext hashes: `52`.
  - Duplicate ciphertext groups: `40`.
  - Offset-skip decompression successes: `0`.
  - Offset-skip plaintext hits: `0`.
  - `simple_offset_skip_route_ruled_out=true`.
  - `lua_payload_decoder_recovered=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round80.yaml`
  - Artifact count: `19`.
  - Evidence refs: `463`.
  - Decoder target artifacts now include `luascripts_payload_variant_corpus`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round81.yaml`
  - Queue item count: `96`.
  - Superseded `luascripts_payload_cipher_profile_target`; added `luascripts_payload_variant_corpus_target=1`.
  - Static trace targets: `12`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_luascripts_variant_corpus.py src/qa_agent/app/summarize_luascripts_payload_variant_corpus.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py tests/test_client_luascripts_variant_corpus.py tests/test_client_evidence_bundle.py tests/test_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_luascripts_variant_corpus tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 221 tests.
- Sensitive path/account-id scan on round79/80/81 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-luascripts-payload-variant-corpus-round79.yaml`
  - SHA-256 `09592d073d4c5d352d3fb2c44858382d9360d456cb47a112ade2567f196216db`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round80.yaml`
  - SHA-256 `3f962bb8b149385f2ee5faf135d93cb3cca9d1473bc7085f8665050ad17b0ef8`
- `ingestion/raw/client_packages/nslg-client-import-queue-round81.yaml`
  - SHA-256 `c7bc2ee54e0c851a795e3edd410ae9fb7485ac1b71397b11b2cdcc4dc5f7455a`

Next step:
- Continue offline/static only.
- Use the 932-variant corpus as decoder validation data once a candidate native decoder is found.
- Prioritize provenance-backed native TextAsset script-buffer owner tracing before xLua loadbuffer.

## 2026-05-21T13:13:08+08:00 - TextAsset payload owner trace import

Slice:
- Materialized external Round173 TextAsset/LuaScripts payload-owner static trace into qa-agent evidence tracking.
- Kept the artifact as decoder-planning/negative route evidence only; no decoded LuaScripts payload or publishable game knowledge was promoted.

Changes:
- Added `src/qa_agent/ingestion/client_textasset_payload_owner_trace.py`.
- Added `src/qa_agent/app/summarize_textasset_payload_owner_trace.py`.
- Added `tests/test_client_textasset_payload_owner_trace.py`.
- Extended client evidence bundle and import queue builders to include `textasset_payload_owner_trace`.
- Updated `ingestion/raw/client_packages/README.md` with round82/83/84 artifacts and rebuild commands.

Generated artifacts:
- `ingestion/raw/client_packages/nslg-textasset-payload-owner-trace-round82.yaml`
  - External round: `173`.
  - Modules scanned: `4`.
  - Conservative terms: `315`.
  - Native string hits: `706`.
  - Exact asset path/stem/filename hits: `0`.
  - Code refs: `0`.
  - Candidate functions: `0`.
  - Payload-owner candidates: `0`.
  - `textasset_payload_owner_proven=false`.
  - `lua_payload_decoder_recovered=false`.
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round83.yaml`
  - Artifact count: `20`.
  - Evidence refs: `464`.
  - Decoder target artifacts now include `textasset_payload_owner_trace`.
- `ingestion/raw/client_packages/nslg-client-import-queue-round84.yaml`
  - Queue item count: `97`.
  - Added `textasset_payload_owner_trace_target=1`.
  - Static trace targets: `13`.

Verification:
- `python3 -m py_compile src/qa_agent/ingestion/client_textasset_payload_owner_trace.py src/qa_agent/app/summarize_textasset_payload_owner_trace.py src/qa_agent/ingestion/client_evidence_bundle.py src/qa_agent/ingestion/client_import_queue.py src/qa_agent/app/build_client_evidence_bundle.py src/qa_agent/app/build_client_import_queue.py tests/test_client_textasset_payload_owner_trace.py tests/test_client_evidence_bundle.py tests/test_client_import_queue.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_client_textasset_payload_owner_trace tests.test_client_evidence_bundle tests.test_client_import_queue -v` passed: 6 tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v` passed: 223 tests.
- Sensitive path/account-id scan on round82/83/84 YAML files found no matches.

Hashes:
- `ingestion/raw/client_packages/nslg-textasset-payload-owner-trace-round82.yaml`
  - SHA-256 `a351f47418682d0602796e9fb8a8409e5bccbdc1e14cee14bcdbb5f3b820bd2d`
- `ingestion/raw/client_packages/nslg-client-evidence-bundle-round83.yaml`
  - SHA-256 `2541df69baf3b70e0c2b942d1d4f774f0f0535c5948d3efaaa01c2a199a68ede`
- `ingestion/raw/client_packages/nslg-client-import-queue-round84.yaml`
  - SHA-256 `13bd6b2a987762482dc420184b952f627256752b1adc51a90496dc917cfd5995`
- `src/qa_agent/ingestion/client_textasset_payload_owner_trace.py`
  - SHA-256 `c77f6d396cf6679e72d978ce87d1ba073800ad67b06f177e4f56c09b9951de91`
- `src/qa_agent/app/summarize_textasset_payload_owner_trace.py`
  - SHA-256 `59104f73a4035a66e450b62e87460aa33dc2fecb64aa87705b23465414dd499f`

Next step:
- Continue offline/static only.
- Shift from broad native string provenance to SerializedFile object layout or managed metadata recovery.
- Require concrete TextAsset/CAB payload pointer plus length provenance before decoder promotion.

## Round 174 - Serialized TextAsset layout imported

Actions:
- Added `src/qa_agent/ingestion/client_serialized_textasset_layout.py` and `src/qa_agent/app/summarize_serialized_textasset_layout.py`.
- Added `tests/test_client_serialized_textasset_layout.py`.
- Added `ingestion/raw/client_packages/nslg-serialized-textasset-layout-round85.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round86.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round87.yaml`.
- Updated bundle/queue builders and README so serialized TextAsset layout is a first-class decoder target.
- Superseded the previous `textasset_payload_owner_trace_target` queue item with `serialized_textasset_layout_probe_target`.

Results:
- Layout match count: `932`.
- Valid layouts: `932`.
- Invalid layouts: `0`.
- Unique object offsets / payload hashes: `52` / `52`.
- Unique stems: `16`.
- Bundle artifacts: `21`.
- Evidence refs: `480`.
- Queue items: `97`.
- Queue target `serialized_textasset_layout_probe_target`: `1`.
- Queue target `textasset_payload_owner_trace_target`: `0`.
- `safe_for_publish=false`; this is route evidence, not publishable gameplay knowledge.

Verification:
- Targeted py_compile passed for new/updated modules and tests.
- Targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `225` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- Sensitive path/account-id scan on round85/86/87 YAML passed with no matches.
- YAML load check passed for round85/86/87.

Hashes:
- `nslg-serialized-textasset-layout-round85.yaml`
  - SHA-256 `332b4b09a4093daed209459357dab0b56ffb27cbc439e6b4dc873c7a40075fda`
- `nslg-client-evidence-bundle-round86.yaml`
  - SHA-256 `713f2e2d8294a6396b44c9646eda8ad7defd68736996f474315983957b8a91a1`
- `nslg-client-import-queue-round87.yaml`
  - SHA-256 `3e9c39c3c9f7a16a13b4a261c6eb9594844610550a373fd6e7ee5a78f77e5d30`
- `src/qa_agent/ingestion/client_serialized_textasset_layout.py`
  - SHA-256 `54225aa29eb8ea353594cbad45e2e1f1b2dcd311bf9dde52b7d4cc5321b36d29`
- `src/qa_agent/app/summarize_serialized_textasset_layout.py`
  - SHA-256 `ab0967aedb7cbac11cd90fc01fa0c26d35d699cfbb690c5b70a69e1690e935c5`
- `tests/test_client_serialized_textasset_layout.py`
  - SHA-256 `89a8f1747d38a67f8338873b7478c77cdd044d3441af02c5e15bdc4adaac9812`

Next step:
- Parse SerializedFile object/preload/container tables to resolve AssetBundle `path_id -> object_offset`.
- Use confirmed TextAsset payload offsets and lengths as decoder-validation anchors.
- Do not promote native payload ownership or Lua decoder status until that mapping and transform route are proven.


## Round 175 - Serialized TextAsset path resolution imported

Actions:
- Added `src/qa_agent/ingestion/client_serialized_textasset_resolution.py` and `src/qa_agent/app/summarize_serialized_textasset_resolution.py`.
- Added `tests/test_client_serialized_textasset_resolution.py`.
- Added `ingestion/raw/client_packages/nslg-serialized-textasset-path-resolution-round88.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round89.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round90.yaml`.
- Updated bundle/queue builders and README so path_id/object_offset resolution is a first-class decoder anchor.
- Superseded `serialized_textasset_layout_probe_target` with `serialized_textasset_path_resolution_target`.

Results:
- Verified container records: `104`.
- Resolved path_id/object_offset records: `104`.
- Unresolved records: `0`.
- Ambiguous records: `0`.
- Unique path IDs: `104`.
- Unique resolved object offsets: `16`.
- Unique resolved payload sha1 hashes: `16`.
- Bundle artifacts: `22`.
- Evidence refs: `584`.
- Queue items: `97`.
- Queue target `serialized_textasset_path_resolution_target`: `1`.
- Queue target `serialized_textasset_layout_probe_target`: `0`.
- `safe_for_publish=false`; this is decoder-route evidence, not publishable gameplay knowledge.

Verification:
- Targeted py_compile passed for new/updated modules and tests.
- Targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `227` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- Sensitive path/account-id scan on round88/89/90 YAML passed with no matches.
- YAML load check passed for round88/89/90.

Hashes:
- `nslg-serialized-textasset-path-resolution-round88.yaml`
  - SHA-256 `50d51b4d10e43808e88e2af10e527715bb61a3277ef8f30d8d88be4b81c8322f`
- `nslg-client-evidence-bundle-round89.yaml`
  - SHA-256 `87f878bea5b5f0e7e2b0cda9244ab3118aef53eb51de683ff05a83d1cb992920`
- `nslg-client-import-queue-round90.yaml`
  - SHA-256 `c5aa691b8c8bddd88ae391eff6d5ed8306ab0ef77f31d968fe5c4e777c4392f4`
- `src/qa_agent/ingestion/client_serialized_textasset_resolution.py`
  - SHA-256 `07c4e5bb353084c1dc65e3dc7b20bd1efff998461e1fd6725a36b9a8a4b0eaad`
- `src/qa_agent/app/summarize_serialized_textasset_resolution.py`
  - SHA-256 `5682697a49602063b76c6185a30e3ce6da99fa075f857958a8bd101bdad8593f`
- `tests/test_client_serialized_textasset_resolution.py`
  - SHA-256 `f8eff71ef6495867c5baa7ddfecfa3996a034c806709a0be44f82cabf001519a`

Next step:
- Use resolved object/payload offsets as exact anchors for native TextAsset script-buffer ownership and LuaScripts decoder recovery.
- Do not return to broad TextAsset string scans.
- Do not promote encrypted payload bytes as gameplay knowledge.


## Round 176 - Resolved payload native anchor scan imported

Actions:
- Added `src/qa_agent/ingestion/client_resolved_payload_native_anchor_scan.py` and `src/qa_agent/app/summarize_resolved_payload_native_anchor_scan.py`.
- Added `tests/test_client_resolved_payload_native_anchor_scan.py`.
- Added `ingestion/raw/client_packages/nslg-resolved-payload-native-anchor-scan-round91.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round92.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round93.yaml`.
- Updated bundle/queue builders and README so resolved payload native-anchor scan is a first-class route artifact.
- Superseded `serialized_textasset_path_resolution_target` with `resolved_payload_native_anchor_scan_target`.

Results:
- Anchors: `368`.
- Strong anchors: `272`.
- Weak anchors: `96`.
- Present native modules: `4`.
- CAB control strong hits, capped: `255`.
- CAB control weak hits, capped: `150`.
- Native strong anchor hits, capped: `0`.
- Native weak numeric hits, capped: `990`.
- Native co-occurrence windows: `0`.
- Native strong co-occurrence windows: `0`.
- Bundle artifacts: `23`.
- Evidence refs: `588`.
- Queue items: `97`.
- Queue target `resolved_payload_native_anchor_scan_target`: `1`.
- Queue target `serialized_textasset_path_resolution_target`: `0`.
- `safe_for_publish=false`; this is route/negative evidence, not publishable gameplay knowledge.

Verification:
- Targeted py_compile passed for new/updated modules and tests.
- Targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `229` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- Sensitive path/account-id scan on round91/92/93 YAML passed with no matches.
- YAML load check passed for round91/92/93.

Hashes:
- `nslg-resolved-payload-native-anchor-scan-round91.yaml`
  - SHA-256 `f32119fafaf92cc6ac73f0e24bb3767bf22a77a29b7ca558c3b36f991a40cb79`
- `nslg-client-evidence-bundle-round92.yaml`
  - SHA-256 `c9f95a118a07b8c2019f95acd63f077a423bff0f6e4d3b0ba7623f045c15121d`
- `nslg-client-import-queue-round93.yaml`
  - SHA-256 `1b1a2adafe56d0cb41f4352d38b753282a77b43368d0abbad18257fb3d4ed425`
- `src/qa_agent/ingestion/client_resolved_payload_native_anchor_scan.py`
  - SHA-256 `72d0c8aa25c98d0f8a0652749c3cfb14c4f1daed883fda4cf58af0101b1fe31c`
- `src/qa_agent/app/summarize_resolved_payload_native_anchor_scan.py`
  - SHA-256 `5b8b872558ff7800daa127279d30281c231dcd94256dfb0adcb6a914dfd8d16e`
- `tests/test_client_resolved_payload_native_anchor_scan.py`
  - SHA-256 `91f75c7a26a246390a67067f515b829a8c843b363dca8d35796a8c743c220eae`

Next step:
- Use resolved payload offsets and lengths for boundary-focused control-flow/method ownership analysis around TextAsset script-buffer APIs and xLua loadbuffer handoff.
- Do not search native binaries for embedded resolved payload constants unless new evidence appears.
- Do not promote encrypted payload bytes as gameplay knowledge.


## Round 177 - TextAsset/xLua boundary ledger imported

Actions:
- Added `src/qa_agent/ingestion/client_textasset_xlua_boundary_ledger.py` and `src/qa_agent/app/summarize_textasset_xlua_boundary_ledger.py`.
- Added `tests/test_client_textasset_xlua_boundary_ledger.py`.
- Added `ingestion/raw/client_packages/nslg-textasset-xlua-boundary-ledger-round94.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round95.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round96.yaml`.
- Updated bundle/queue builders and client package README so the Round177 boundary ledger is a first-class route artifact.
- Superseded `resolved_payload_native_anchor_scan_target` with `textasset_xlua_boundary_ledger_target`.

Results:
- Boundary ledger route records: `6`.
- Closed negative routes: `4`.
- Blocked pending metadata routes: `1`.
- Next viable routes: `1`.
- Proven payload-owner routes: `0`.
- Exact native anchor hits: `0`.
- Resolver payload-owner candidates: `0`.
- Bundle artifacts: `24`.
- Evidence refs: `594`.
- Queue items: `97`.
- Queue target `textasset_xlua_boundary_ledger_target`: `1`.
- Queue target `resolved_payload_native_anchor_scan_target`: `0`.
- `safe_for_publish=false`; this is route/negative planning evidence, not publishable gameplay knowledge.

Verification:
- Targeted py_compile passed for new/updated modules and tests.
- Targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `231` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- Sensitive path/account-id scan on round94/95/96 YAML passed with no matches.
- YAML load check passed for round94/95/96.

Hashes:
- `nslg-textasset-xlua-boundary-ledger-round94.yaml`
  - SHA-256 `a67b22013716840bf59e3a8b31705b3d05152cb3fad2d50058856be104461cda`
- `nslg-client-evidence-bundle-round95.yaml`
  - SHA-256 `9e0e1ad1f661d7b0b4e2d87c09409a607e0f88f7f02627bddd84557928e4edc9`
- `nslg-client-import-queue-round96.yaml`
  - SHA-256 `741ea7b24b453f704c25a2e5aa96756f26f3b9f25fd796e4be50b49ab6826709`
- `src/qa_agent/ingestion/client_textasset_xlua_boundary_ledger.py`
  - SHA-256 `22c31e1be8af4b8f9294fefae498100de11fbeaa80fa05c1f7c9186076b0125c`
- `src/qa_agent/app/summarize_textasset_xlua_boundary_ledger.py`
  - SHA-256 `f88b0d0d277887e43947446c4c709ebcdaabe9b72d0861d8cd635438cd85cd50`
- `tests/test_client_textasset_xlua_boundary_ledger.py`
  - SHA-256 `5b617d420479968705f744920be4e3506b3ddc78d7ac6306afa3de37413003e1`

Next step:
- Recover protected metadata/method ownership for InitLuaEnv/TextAsset script-buffer APIs.
- Use resolved object/payload offsets and lengths only as validation anchors after an owner candidate appears.
- Do not repeat broad native string scans or embedded resolved-payload constant scans.


## Round 178 - RuntimeInitializeOnLoads registry probe imported

Actions:
- Added `src/qa_agent/ingestion/client_runtime_init_registry_probe.py` and `src/qa_agent/app/summarize_runtime_init_registry_probe.py`.
- Added `tests/test_client_runtime_init_registry_probe.py`.
- Added `ingestion/raw/client_packages/nslg-runtime-init-registry-probe-round97.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round98.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round99.yaml`.
- Updated bundle/queue builders and client package README so Round178 registry evidence is a first-class runtime-init route artifact.
- Superseded `runtime_init_metadata_route_target` with `runtime_init_registry_probe_target` in the queue when the registry confirms managed InitLuaEnv but has no native address/token fields.

Results:
- RuntimeInitialize entries: `12`.
- InitLuaEnv registry entries: `1`.
- Registry native address/token fields: `0`.
- UnityPlayer registry filename code refs: `1`.
- Bundle artifacts: `25`.
- Evidence refs: `598`.
- Queue items: `97`.
- Queue target `runtime_init_registry_probe_target`: `1`.
- Queue target `runtime_init_metadata_route_target`: `0`.
- `safe_for_publish=false`; this is runtime-init planning evidence, not publishable gameplay knowledge.

Verification:
- External `py_compile` and `json.tool` passed for Round178 artifacts.
- External Round178 sensitive marker scan found no phone/credential/server_id/role_id matches.
- Targeted py_compile passed for new/updated modules and tests.
- Targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `233` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- Sensitive path/account marker scan on round97/98/99 YAML passed with no matches.
- YAML load check passed for round97/98/99.

Hashes:
- `nslg-runtime-init-registry-probe-round97.yaml`
  - SHA-256 `e4c5af0e929edfcbe7f8ce0826b245ae1b95eaa9f949328ff86db5bff0a7b032`
- `nslg-client-evidence-bundle-round98.yaml`
  - SHA-256 `ee0a37aa50b119c5da9aacdc414e8270ef572c5bb66fae18c9afb90dc53689b2`
- `nslg-client-import-queue-round99.yaml`
  - SHA-256 `3f90b8c4275dd984a37fc3612aba3dd9ee8236a482bbe6d6874d8b7f1cdfb8a0`
- `src/qa_agent/ingestion/client_runtime_init_registry_probe.py`
  - SHA-256 `1b506071e8ea8bcfe2493e082970fac80a7c45fa3cb3b695e204ac7105b476b3`
- `src/qa_agent/app/summarize_runtime_init_registry_probe.py`
  - SHA-256 `c173c5d85e76d08b78e6c370a470146bf76effe27b29ed8f807cba962a18d88e`
- `tests/test_client_runtime_init_registry_probe.py`
  - SHA-256 `fb75e971d61ae00d63b2135f8af6fb303ecabc62fc979fdca8f7c76907ebe0e6`

Next step:
- Recover protected metadata or IL2CPP registration ownership for InitLuaEnv/TextAsset script-buffer APIs.
- Treat RuntimeInitializeOnLoads.json as a managed-name anchor only; do not repeat direct registry-to-native-address or broad native string scans.


## Round 179 - GameAssembly CodeGenModule probe imported

Actions:
- Added `src/qa_agent/ingestion/client_codegen_module_probe.py` and `src/qa_agent/app/summarize_gameassembly_codegen_module_probe.py`.
- Added `tests/test_client_codegen_module_probe.py`.
- Added `ingestion/raw/client_packages/nslg-gameassembly-codegen-module-probe-round100.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round101.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round102.yaml`.
- Updated bundle/queue builders and client package README so Round179 CodeGenModule evidence is a first-class IL2CPP registration-route artifact.
- Superseded `runtime_init_registry_probe_target` with `gameassembly_codegen_module_probe_target` when Assembly-CSharp CodeGenModule records are present.

Results:
- CodeGenModule-like candidates: `95`.
- Contiguous CodeGenModule pointer runs: `4`.
- Largest run: `49` modules.
- Assembly-CSharp modules: `2`.
- Assembly-CSharp method pointers: `30078`.
- Assembly-CSharp executable method pointers: `29351`.
- Assembly-CSharp null method pointers: `727`.
- Assembly-CSharp-firstpass method pointers: `354`.
- Bundle artifacts: `26`.
- Evidence refs: `602`.
- Queue items: `97`.
- Queue target `gameassembly_codegen_module_probe_target`: `1`.
- Queue target `runtime_init_registry_probe_target`: `0`.
- `safe_for_publish=false`; this is IL2CPP registration planning evidence, not publishable gameplay knowledge.

Verification:
- External `py_compile` and `json.tool` passed for Round179 artifacts.
- External Round179 sensitive marker scan found no phone/credential/server_id/role_id matches.
- Targeted py_compile passed for new/updated modules and tests.
- Targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `235` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- Sensitive path/account marker scan on round100/101/102 YAML passed with no matches.
- YAML load check passed for round100/101/102.

Hashes:
- `nslg-gameassembly-codegen-module-probe-round100.yaml`
  - SHA-256 `5c7632eb6649f68d2ab57915bc36a33aae44fda27f99c3898c9fe6eacc424498`
- `nslg-client-evidence-bundle-round101.yaml`
  - SHA-256 `ac3040ba81d11838dcba6d243e1662b4b7d71cc44e6b62065295f877e1203806`
- `nslg-client-import-queue-round102.yaml`
  - SHA-256 `5fbb357068a614a2e25e8c0afd3894ebcb123d557d52324273c73901a60e2c0c`
- `src/qa_agent/ingestion/client_codegen_module_probe.py`
  - SHA-256 `74c5e59e63ecb5b699a46fa5fdcc3dc1807a5e6d9614ffb825b4c75ce5cb00c1`
- `src/qa_agent/app/summarize_gameassembly_codegen_module_probe.py`
  - SHA-256 `fab5bcd1343d7ea0ee42a1b8dfa52ecf990c2f9b81000a39e91481a8fb58af63`
- `tests/test_client_codegen_module_probe.py`
  - SHA-256 `5f983165bdbeec714fa21be9392149c980992fc4aa99c2c87a6e53b6ec0d509b`

Next step:
- Recover protected metadata string/method-definition tables or metadata-registration index maps.
- Use Assembly-CSharp CodeGenModule method pointer tables as registration-side anchors only.
- Do not infer `InitLuaEnv` ownership until decoded metadata proves the mapping.


## Round 180 - GameAssembly registration anchor probe imported

Actions:
- Added `src/qa_agent/ingestion/client_registration_anchor_probe.py` and `src/qa_agent/app/summarize_gameassembly_registration_anchor_probe.py`.
- Added `tests/test_client_registration_anchor_probe.py`.
- Added `ingestion/raw/client_packages/nslg-gameassembly-registration-anchor-probe-round103.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round104.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round105.yaml`.
- Updated bundle/queue builders and client package README so Round180 registration-anchor evidence is a first-class IL2CPP registration-route artifact.
- Superseded `gameassembly_codegen_module_probe_target` with `gameassembly_registration_anchor_probe_target` when the stronger CodeRegistration-side anchor is present.

Results:
- CodeGenModules field candidates: `1`.
- Declared CodeGenModules: `98`.
- Parsed CodeGenModules: `98`.
- Nonzero-method modules: `96`.
- Assembly-CSharp module index: `5`.
- Assembly-CSharp method pointers: `30078`.
- Registration anchor code refs: `0`.
- MetadataRegistration candidates: `0`.
- Bundle artifacts: `27`.
- Evidence refs: `605`.
- Queue items: `97`.
- Queue target `gameassembly_registration_anchor_probe_target`: `1`.
- Queue target `gameassembly_codegen_module_probe_target`: `0`.
- `safe_for_publish=false`; this is IL2CPP registration planning evidence, not publishable gameplay knowledge.

Verification:
- External `py_compile` and `json.tool` passed for Round180 artifacts.
- External Round180 sensitive marker scan found no phone/credential/server_id/role_id matches.
- Targeted py_compile passed for new/updated modules and tests.
- Targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `237` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- Sensitive path/account marker scan on round103/104/105 YAML passed with no matches.
- YAML load check passed for round103/104/105.

Hashes:
- `nslg-gameassembly-registration-anchor-probe-round103.yaml`
  - SHA-256 `71ba392c882a425985650aa9bf5a63d91ffff63091583fbd91601a6c6c4d4738`
- `nslg-client-evidence-bundle-round104.yaml`
  - SHA-256 `8f1fb7befe4f74af14e4992212873c4755760a02f75a7b997ffc83d81cbb2732`
- `nslg-client-import-queue-round105.yaml`
  - SHA-256 `5d8870d58ea2bc5d89bac6ad1573379d70894e14f3c38a94855652c7d2843516`
- `src/qa_agent/ingestion/client_registration_anchor_probe.py`
  - SHA-256 `fa043f7abcd61081f405161cc09fccd9e108858e66f594b12f15a0de6ffe14a1`
- `src/qa_agent/app/summarize_gameassembly_registration_anchor_probe.py`
  - SHA-256 `45be2069a6ba24f035bfaab881b775b1f2f538de4ed750b4063e3ce5d6b5cf30`
- `tests/test_client_registration_anchor_probe.py`
  - SHA-256 `cf227878381329a4bff9f20b855f966f367a38ebd5b76b47995ceb203a6ee789`

Next step:
- Recover CodeRegistration/MetadataRegistration callsite pairing or decoded protected metadata method-definition ownership.
- Use Round180 CodeGenModules anchors as registration-side evidence only.
- Do not infer `InitLuaEnv` ownership until decoded metadata proves the mapping.

## Round 181 - GameAssembly registration layout probe imported

Actions:
- Added `src/qa_agent/ingestion/client_registration_layout_probe.py` and `src/qa_agent/app/summarize_gameassembly_registration_layout_probe.py`.
- Added `tests/test_client_registration_layout_probe.py`.
- Added `ingestion/raw/client_packages/nslg-gameassembly-registration-layout-probe-round106.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round107.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round108.yaml`.
- Updated bundle/queue builders and client package README so Round181 registration-layout evidence is a first-class IL2CPP registration-route artifact.
- Superseded `gameassembly_registration_anchor_probe_target` with `gameassembly_registration_layout_probe_target` when the refined CodeRegistration layout is present.

Results:
- Primary CodeRegistration-like start: `0x4332730`.
- Round180 owner inference corrected: previous `0x4332718` is not the exact structure start.
- CodeGenModules count/pointer field: `+0x78/+0x80`.
- Known CodeGenModules count: `98`.
- Registration static code refs: `0`.
- Registration raw VA refs: `7`.
- MetadataRegistration-like candidate windows: `58,746`, weak/unpaired.
- MetadataRegistration paired by callsite: `false`.
- InitLuaEnv method pointer recovered: `false`.
- Bundle artifacts: `28`.
- Evidence refs: `609`.
- Queue items: `97`.
- Queue target `gameassembly_registration_layout_probe_target`: `1`.
- Queue target `gameassembly_registration_anchor_probe_target`: `0`.
- Queue target `gameassembly_codegen_module_probe_target`: `0`.
- `safe_for_publish=false`; this is IL2CPP registration layout planning evidence, not publishable gameplay knowledge.

Verification:
- External `py_compile` and `json.tool` passed for Round181 artifacts.
- External Round181 sensitive marker scan found no phone/credential/server_id/role_id matches.
- Targeted py_compile passed for new/updated modules and tests.
- Targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `239` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- Sensitive path/account marker scan on round106/107/108 YAML passed with no matches.
- YAML load check passed for round106/107/108.

Hashes:
- `nslg-gameassembly-registration-layout-probe-round106.yaml`
  - SHA-256 `8b970041b834b6436d30921d5ac6927082d5e68cef397c766e49dbdf4026d4a9`
- `nslg-client-evidence-bundle-round107.yaml`
  - SHA-256 `6a67867218208e375cf21ea4ae29537c88f5cd2bfca3769d8f36b49d3041eb2e`
- `nslg-client-import-queue-round108.yaml`
  - SHA-256 `cd3e65de63a008e71f24cd6d6c40043bf8e2a2506872d65993eb5884e4b7c70f`
- `src/qa_agent/ingestion/client_registration_layout_probe.py`
  - SHA-256 `678f55fec76008c12f3419df71d07c12822bacd878ab01d8dadbe2e570e4ab47`
- `src/qa_agent/app/summarize_gameassembly_registration_layout_probe.py`
  - SHA-256 `a548854541bedf675ab5271c78aa37b79dae923310825c734f8e2bcda91b56d7`
- `tests/test_client_registration_layout_probe.py`
  - SHA-256 `a2fe6b72902204a6071ed41208e9804957f870b682c2bc10f7985624bf690220`

Next step:
- Recover a CodeRegistration/MetadataRegistration callsite pair or decoded protected metadata method-definition ownership.
- Use `0x4332730` as the CodeRegistration-side layout anchor only.
- Do not infer `InitLuaEnv` ownership until decoded metadata proves the mapping.

## Round 182 - GameAssembly registration pair-context probe imported

Actions:
- Added `src/qa_agent/ingestion/client_registration_pair_context_probe.py` and `src/qa_agent/app/summarize_gameassembly_registration_pair_context_probe.py`.
- Added `tests/test_client_registration_pair_context_probe.py`.
- Added `ingestion/raw/client_packages/nslg-gameassembly-registration-pair-context-probe-round109.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round110.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round111.yaml`.
- Superseded `gameassembly_registration_layout_probe_target` with `gameassembly_registration_pair_context_probe_target`.

Results:
- Raw CodeRegistration start refs: `0`.
- Raw metadata-candidate refs: `25`.
- Registration code refs: `0`.
- Metadata candidate code refs: `0`.
- Paired pointer neighborhoods: `0`.
- Call argument pair windows: `0`.
- Metadata ref family clusters: `17`.
- Registration pair recovered: `false`.
- Bundle artifacts: `29`; evidence refs: `613`; queue items: `97`.
- Queue target `gameassembly_registration_pair_context_probe_target`: `1`.
- `safe_for_publish=false`; this is IL2CPP registration route-closure evidence, not publishable gameplay knowledge.

Verification:
- External Round182 `py_compile`, `json.tool`, and sensitive marker scan passed.
- Targeted py_compile and targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `241` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load and sensitive path/account marker scan passed for round109/110/111.

Hashes:
- `nslg-gameassembly-registration-pair-context-probe-round109.yaml`
  - SHA-256 `b3e556a4d041538a946eee141974b11c03ed2222b78d58141f9eb7097e2c5950`
- `nslg-client-evidence-bundle-round110.yaml`
  - SHA-256 `3109720b7a48b8828ec448ea7b50149fbb77a6b618ad37fd318d25ae27bcf6ee`
- `nslg-client-import-queue-round111.yaml`
  - SHA-256 `6a5e3e5dd7a4fa282aee11160b78a99ac4136133a97d37572a8751a95baccda1`

Next step:
- Pivot from direct pointer-pair xrefs to decoded protected metadata method-definition ownership or a broader bounded IL2CPP initialization dispatcher trace.
- Do not infer `InitLuaEnv` ownership until decoded metadata proves the mapping.

## Round 183 - GameAssembly initializer-dispatch trace imported

Actions:
- Added `src/qa_agent/ingestion/client_initializer_dispatch_trace.py` and `src/qa_agent/app/summarize_gameassembly_initializer_dispatch_trace.py`.
- Added `tests/test_client_initializer_dispatch_trace.py`.
- Added `ingestion/raw/client_packages/nslg-gameassembly-initializer-dispatch-trace-round112.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round113.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round114.yaml`.
- Updated bundle/queue builders and `ingestion/raw/client_packages/README.md`.

Results:
- Function rows scanned: `290472`.
- Instructions scanned: `16265170`.
- Registration anchor ref functions: `0`.
- Metadata candidate ref functions: `0`.
- Global-metadata string ref functions: `2`.
- Entry/export-root to registration path found: `false`.
- Entry/export-root to metadata candidate path found: `false`.
- Non-exec function pointer hits: `0`.
- Dispatcher candidates: `24`.
- Initializer dispatcher route recovered: `false`.
- InitLuaEnv method pointer recovered: `false`.
- Bundle artifacts: `30`; evidence refs: `618`; queue items: `98`.
- Queue target `gameassembly_initializer_dispatch_trace_target`: `1`.
- `safe_for_publish=false`; this is IL2CPP initializer-dispatch route-closure evidence, not publishable gameplay knowledge.

Verification:
- External Round183 `py_compile`, `json.tool`, and sensitive marker scan passed.
- Targeted py_compile and targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `243` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load check passed for round112/113/114.
- Sensitive marker scan passed for round112/113/114 and touched source/test/README files.

Hashes:
- `nslg-gameassembly-initializer-dispatch-trace-round112.yaml`
  - SHA-256 `c38e0b35af93e97ca1a310cec5912370514dac79f1ec0cc678b03a06a6dbe062`
- `nslg-client-evidence-bundle-round113.yaml`
  - SHA-256 `dd8feb98f9507f1e8d70dfd35cf03755e472902f596b0333ef6980daf73d6885`
- `nslg-client-import-queue-round114.yaml`
  - SHA-256 `da4a8f8489075002b7a5c606582f930936b18efb1f0d5722e3df4bcb7afa3214`
- `src/qa_agent/ingestion/client_initializer_dispatch_trace.py`
  - SHA-256 `e0878250ffe45dc913575933e7f126967059899a36ee2921f69c9540cbf1e978`
- `src/qa_agent/app/summarize_gameassembly_initializer_dispatch_trace.py`
  - SHA-256 `7e59bd9ea305a62f2bf3504e7dc1d5b4810335a8d23fb479e49d3ed8e626c856`
- `tests/test_client_initializer_dispatch_trace.py`
  - SHA-256 `894fe61f045f98a0f8b67a4c5824a3ff594d9dd0604b242f9d0535923b3a7c06`

Next step:
- Pivot from bounded direct-call dispatcher tracing to decoded protected metadata method-definition ownership or bounded indirect initializer table decoding.
- Do not infer `InitLuaEnv` ownership until decoded metadata proves the mapping.



## Round 184 - GameAssembly function-pointer-table probe imported

Actions:
- Added `src/qa_agent/ingestion/client_function_pointer_table_probe.py` and `src/qa_agent/app/summarize_gameassembly_function_pointer_table_probe.py`.
- Added `tests/test_client_function_pointer_table_probe.py`.
- Added `ingestion/raw/client_packages/nslg-gameassembly-function-pointer-table-probe-round115.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round116.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round117.yaml`.
- Updated bundle/queue builders and `ingestion/raw/client_packages/README.md`.

Results:
- Function-pointer hits: `342009` across `57759` runs.
- Known CodeGenModule method tables: `96`; hits inside: `133465`.
- Known CodeRegistration field arrays: `6`; hits inside: `172773`.
- Relevant dispatcher pointer hits: `22`.
- Dispatcher hits outside known IL2CPP tables: `0`.
- Global-metadata string-ref function pointer hits: `0`.
- Independent initializer table candidates: `0`.
- InitLuaEnv method pointer recovered: `false`.
- Bundle artifacts: `31`; evidence refs: `622`; queue items: `99`.
- Queue target `gameassembly_function_pointer_table_probe_target`: `1`.
- `safe_for_publish=false`; this is IL2CPP route-closure evidence, not publishable gameplay knowledge.

Verification:
- External Round184 `py_compile`, `json.tool`, and sensitive marker scan passed.
- Targeted py_compile and targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `245` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load check passed for round115/116/117.
- Sensitive marker scan passed for round115/116/117 and touched source/test/README files.

Hashes:
- `nslg-gameassembly-function-pointer-table-probe-round115.yaml`
  - SHA-256 `b7b0f0e977e101d19b4f281b23fbf6d9bda16e9b347218e6e9f7081174cfc83e`
- `nslg-client-evidence-bundle-round116.yaml`
  - SHA-256 `3eacdb8a336b9e870c7aa0d6db2bd32e3a01aae917bc900cf00f04a2260a169f`
- `nslg-client-import-queue-round117.yaml`
  - SHA-256 `fded1494bc6b0bda812232c17f29d5a4cc33a8d8dbfb4b5a0ca1bb0979adda36`
- `src/qa_agent/ingestion/client_function_pointer_table_probe.py`
  - SHA-256 `c3af9f2ae76f1e41377297bc238b6c634d4af06f6b1b77e4921fe6724ad0120b`
- `src/qa_agent/app/summarize_gameassembly_function_pointer_table_probe.py`
  - SHA-256 `1525eaace4a4c3035a0a5e5e4763f4138ec27e220ed028ec5a192657e06e6fab`
- `tests/test_client_function_pointer_table_probe.py`
  - SHA-256 `ed5c68b843e632d8805e08ed1a80707a6e186ec0fd8d5f4c607373b36a0fb061`

Next step:
- Continue offline/static only.
- Pivot to decoded protected metadata method-definition ownership or a more specific metadata-registration bridge.
- Do not infer `InitLuaEnv` ownership from CodeGenModule or CodeRegistration table membership.
## Round 185 - GameAssembly MetadataRegistration candidate taxonomy imported

Actions:
- Added `src/qa_agent/ingestion/client_metadata_registration_candidate_taxonomy.py` and `src/qa_agent/app/summarize_gameassembly_metadata_registration_candidate_taxonomy.py`.
- Added `tests/test_client_metadata_registration_candidate_taxonomy.py`.
- Added `ingestion/raw/client_packages/nslg-gameassembly-metadata-registration-candidate-taxonomy-round118.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round119.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round120.yaml`.
- Updated bundle/queue builders, tests, and `ingestion/raw/client_packages/README.md`.

Results:
- Metadata candidate windows scanned: `58879`.
- Exact-ref candidates: `12`; exact-ref non-tiny candidates: `0`; exact-ref max count: `15`.
- High-count candidates: `182`; strong high-count candidates: `169`; referenced high-count candidates: `0`.
- MetadataRegistration owner recovered: `false`.
- InitLuaEnv method pointer recovered: `false`.
- Bundle artifacts: `32`; evidence refs: `626`; queue items: `100`.
- Queue target `gameassembly_metadata_registration_candidate_taxonomy_target`: `1`.
- `safe_for_publish=false`; this is IL2CPP route-taxonomy evidence, not publishable gameplay knowledge.

Verification:
- External Round185 `py_compile`, `json.tool`, and literal account/password marker scan passed.
- Targeted py_compile and targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `247` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load check passed for round118/119/120.
- Sensitive marker scan found no literal account/password/server/role markers; generic `token/credentials` occurrences are existing guardrail or IL2CPP field-name text.

Hashes:
- `nslg-gameassembly-metadata-registration-candidate-taxonomy-round118.yaml`
  - SHA-256 `8ce548b22d8705b6ef00c7b28a7eacb5278b3b4c5272a88953a2a908c1c44a3b`
- `nslg-client-evidence-bundle-round119.yaml`
  - SHA-256 `50a49e22647752769cc8c7d2fdacf25d0fb3df9bb03293ffba5e434eaf09ffd6`
- `nslg-client-import-queue-round120.yaml`
  - SHA-256 `0f3e02b4074279c050209566938ce865af32d8b8d831e477ddde844b8315902d`
- `src/qa_agent/ingestion/client_metadata_registration_candidate_taxonomy.py`
  - SHA-256 `be413748fe66591d017f9914e340569957f1ec23fbd052288a0ab052bdb7887e`
- `src/qa_agent/app/summarize_gameassembly_metadata_registration_candidate_taxonomy.py`
  - SHA-256 `36c3793891403349db0558b10a3e98ef14120ce9829cd826f40ec37bc4c46b9c`
- `tests/test_client_metadata_registration_candidate_taxonomy.py`
  - SHA-256 `ef279263d97dfaf1c7e98f56059d161d1f1b520afcfb5e102f61cb3065b433c9`

Next step:
- Continue offline/static only.
- Pivot from top MetadataRegistration-like window candidates to protected global-metadata decode or a proven MetadataRegistration owner/callsite.
- Do not infer `InitLuaEnv` ownership from tiny-count exact-ref candidates or unowned high-count windows.

## Round 186 - NEP2 vector/helper candidate provenance imported

Actions:
- Added `src/qa_agent/ingestion/client_nep2_vector_candidate_provenance.py` and `src/qa_agent/app/summarize_nep2_vector_candidate_provenance.py`.
- Added `tests/test_client_nep2_vector_candidate_provenance.py`.
- Added `ingestion/raw/client_packages/nslg-nep2-vector-candidate-provenance-round121.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round122.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round123.yaml`.
- Updated bundle/queue builders, tests, and `ingestion/raw/client_packages/README.md`.

Results:
- Targets inspected: `17`; vector/helper candidates: `9`.
- Provenance-linked targets: `1`, but it reaches a file helper and not a vector transform.
- Provenance-linked vector candidates: `0`.
- Metadata/Lua keyword-ref targets: `0`.
- Read/mapping import targets: `2`.
- Bundle artifacts: `33`; evidence refs: `644`; queue items: `101`.
- Queue target `nep2_vector_candidate_provenance_target`: `1`.
- `safe_for_publish=false`; this is route/provenance evidence, not publishable gameplay knowledge.

Verification:
- External Round186 `py_compile`, `json.tool`, and literal account/password marker scan passed.
- Targeted py_compile and targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `249` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load check passed for round121/122/123.
- Sensitive marker scan found no literal account/password/server/role data; generic `account/credentials` occurrences are guardrail text.

Hashes:
- `nslg-nep2-vector-candidate-provenance-round121.yaml`
  - SHA-256 `b3d329b22301292765ba4b51fb4973cf4d043c8d77ffdbea4a3d3b1610988cd3`
- `nslg-client-evidence-bundle-round122.yaml`
  - SHA-256 `f8bd53ef5b571eebba395aba8acdf1a79f274cddbda871c43e5b75c7e6da95d2`
- `nslg-client-import-queue-round123.yaml`
  - SHA-256 `f67ae47220fed14ddce1b687213cd0c23cb0d680aecefcd22cde828f804a2787`
- `src/qa_agent/ingestion/client_nep2_vector_candidate_provenance.py`
  - SHA-256 `723e825daebcbc335f33c8349d67c783c53f741f92831f0e711913eb64737a14`
- `src/qa_agent/app/summarize_nep2_vector_candidate_provenance.py`
  - SHA-256 `36986ddb1b21b34ff9dd9b7c07c8524d54ae87f7334c84f54b437eb5f43ce7a8`
- `tests/test_client_nep2_vector_candidate_provenance.py`
  - SHA-256 `297970940bfd16ba167a0d6d1d732d3bc432ed734cb1d00eb8396db6b48cbbcf`

Next step:
- Continue offline/static only.
- Recover payload-buffer ownership around TextAsset/LuaScripts or protected global-metadata before decoder promotion.

## Round 187 - NEP2 file-helper caller provenance imported

Actions:
- Added `src/qa_agent/ingestion/client_nep2_file_helper_caller_provenance.py` and `src/qa_agent/app/summarize_nep2_file_helper_caller_provenance.py`.
- Added `tests/test_client_nep2_file_helper_caller_provenance.py`.
- Added `ingestion/raw/client_packages/nslg-nep2-file-helper-caller-provenance-round124.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round125.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round126.yaml`.
- Updated bundle/queue builders, tests, and `ingestion/raw/client_packages/README.md`.

Results:
- Targets inspected: `24`; helper seed targets: `3`.
- Caller paths to helper: `4`; callee paths from helper: `19`.
- Payload keyword-ref functions: `0`.
- CreateFile import functions: `1`; read/mapping import functions: `2`.
- File-helper payload owner proven: `false`.
- Bundle artifacts: `34`; evidence refs: `669`; queue items: `102`.
- Queue target `nep2_file_helper_caller_provenance_target`: `1`.
- `safe_for_publish=false`; this is route-closure evidence, not publishable gameplay knowledge.

Verification:
- External Round187 `py_compile`, `json.tool`, and literal account/password marker scan passed.
- Targeted py_compile and targeted unittest passed: `8` tests.
- Full qa-agent unittest passed: `251` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load check passed for round124/125/126.
- Sensitive marker scan found no literal account/password data; generic `token` occurrences are guardrail or IL2CPP field-name text.

Hashes:
- `nslg-nep2-file-helper-caller-provenance-round124.yaml`
  - SHA-256 `f5358fcc98b1323e4949ef7ed4cc739be156e81341c21d6dbd073182eba7d9aa`
- `nslg-client-evidence-bundle-round125.yaml`
  - SHA-256 `68079ca5fbb13845c19ba8f51d3f1f73aed3c9f265aad24484f69ef6b511ae2e`
- `nslg-client-import-queue-round126.yaml`
  - SHA-256 `34a019e353ef93c8eb834da31b653429adccfda9ee5fd6ff04c0cbd7f01684d4`
- `src/qa_agent/ingestion/client_nep2_file_helper_caller_provenance.py`
  - SHA-256 `e14275408347375c13fac3da6d64379b6a9dd192b8dfff6067c6702d1dc36291`
- `src/qa_agent/app/summarize_nep2_file_helper_caller_provenance.py`
  - SHA-256 `12a4ccdbc01474cc597f417c50ce862afa795d2f4499e3667497c6c4f01c5f76`
- `tests/test_client_nep2_file_helper_caller_provenance.py`
  - SHA-256 `339a142922e84c903ff299947cfdc604031c3489c1f05a054193e318d6a33852`

Next step:
- Continue offline/static only.
- Keep NEP2 `0xda90`/`0xd720` demoted as generic file-helper evidence.
- Prioritize GameAssembly MetadataRegistration / protected global-metadata ownership or a proven TextAsset/LuaScripts payload owner.

## Round 188 - GameAssembly global-metadata owner probe imported

Actions:
- Added `src/qa_agent/ingestion/client_gameassembly_global_metadata_owner_probe.py` and `src/qa_agent/app/summarize_gameassembly_global_metadata_owner_probe.py`.
- Added `tests/test_client_gameassembly_global_metadata_owner_probe.py`.
- Added `ingestion/raw/client_packages/nslg-gameassembly-global-metadata-owner-probe-round127.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round128.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round129.yaml`.
- Updated bundle/queue builders, tests, and `ingestion/raw/client_packages/README.md`.

Results:
- Targets inspected: `2`; seed functions: `2`.
- Metadata string-ref functions: `2`.
- File/mapping API functions: `0`.
- MetadataRegistration candidate-ref functions: `0`.
- Loader owner candidates: `0`.
- `global_metadata_owner_candidate_found=false`; `safe_for_publish=false`.
- Bundle artifacts: `35`; evidence refs: `672`; queue items: `103`.
- Queue target `gameassembly_global_metadata_owner_probe_target`: `1`.

Verification:
- External Round188 `py_compile`, `json.tool`, and literal account/password marker scan passed.
- Targeted py_compile and targeted unittest passed: `6` tests.
- Full qa-agent unittest passed: `253` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load check passed for round127/128/129.
- Sensitive marker scan found no literal account/password values in touched source/test/YAML outputs.

Hashes:
- `nslg-gameassembly-global-metadata-owner-probe-round127.yaml`
  - SHA-256 `5dafef54cacdc08cd218400d47e0eac9b764c3da25aefcf946ba97e21ec7b25e`
- `nslg-client-evidence-bundle-round128.yaml`
  - SHA-256 `efb5a347ec492ea93fb1b543dcb51d827cd22721ba2f4a4ccb6d988436517a2f`
- `nslg-client-import-queue-round129.yaml`
  - SHA-256 `e7ae9b0f97a9fbdaf5b11d046ba18793bcfc3f579e04ff3b4be20bd36dc7e6a3`
- `src/qa_agent/ingestion/client_gameassembly_global_metadata_owner_probe.py`
  - SHA-256 `d2b8f961e41a0345800da096901c43b38f1c711b753f7c1454a0895e7cb1d91b`
- `src/qa_agent/app/summarize_gameassembly_global_metadata_owner_probe.py`
  - SHA-256 `863461c56b91748373d733ca72a0878da5ecf47c687c309d9586c9c1df31cc1d`
- `tests/test_client_gameassembly_global_metadata_owner_probe.py`
  - SHA-256 `cd258a5a59e8c2b7f713f3ffc73b3d0fb54c7e1fb362e10c2d522a6168728cac`

Next step:
- Continue offline/static only.
- Do not promote `global-metadata.dat` string refs alone as loader ownership.
- Prioritize protected metadata method-definition ownership, a proven file-buffer owner, or TextAsset/LuaScripts payload owner before decoder promotion.

## Round 189 - NEP2 vector wrapper owner probe imported

Actions:
- Added `src/qa_agent/ingestion/client_nep2_vector_wrapper_owner_probe.py` and `src/qa_agent/app/summarize_nep2_vector_wrapper_owner_probe.py`.
- Added `tests/test_client_nep2_vector_wrapper_owner_probe.py`.
- Added `ingestion/raw/client_packages/nslg-nep2-vector-wrapper-owner-probe-round130.yaml`.
- Rebuilt `ingestion/raw/client_packages/nslg-client-evidence-bundle-round131.yaml` and `ingestion/raw/client_packages/nslg-client-import-queue-round132.yaml`.
- Updated bundle/queue builders, tests, and `ingestion/raw/client_packages/README.md`.

Results:
- Vector targets from Round186: `11`.
- Wrapper functions inspected: `13`; direct vector wrappers: `12`.
- Vector call edges: `59`.
- Payload/owner candidates: `0`; keyword-linked wrappers: `0`; read/mapping-import wrappers: `0`; read-seed provenance paths: `0`.
- `vector_wrapper_payload_owner_proven=false`; `safe_for_publish=false`.
- Bundle artifacts: `36`; evidence refs: `686`; queue items: `104`.
- Queue target `nep2_vector_wrapper_owner_probe_target`: `1`.

Verification:
- External Round189 `py_compile`, `json.tool`, and literal account/password marker scan passed.
- Targeted py_compile and targeted unittest passed: `10` tests.
- Full qa-agent unittest passed: `255` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load check passed for round130/131/132.
- Sensitive marker scan found no literal account/password data; generic `credentials` appears only in guardrail text.

Hashes:
- `nslg-nep2-vector-wrapper-owner-probe-round130.yaml`
  - SHA-256 `f695aebf2a748bc1623c95e107b5ee351509b5f4b142196d00a23fc189805fb8`
- `nslg-client-evidence-bundle-round131.yaml`
  - SHA-256 `21fe88f5fbbafe1aadeb44cf57fc645c7c1c451bf1578c7a13099943cbb35a7c`
- `nslg-client-import-queue-round132.yaml`
  - SHA-256 `f5ea51db4a97c4ec03d1f1a62c7e117046c348e462ba33c2c53ce3a299182c43`
- `src/qa_agent/ingestion/client_nep2_vector_wrapper_owner_probe.py`
  - SHA-256 `1553252f7e23062e44fc03fd331fc69320f568413e36cca7467041ad184f752c`
- `src/qa_agent/app/summarize_nep2_vector_wrapper_owner_probe.py`
  - SHA-256 `370ae746667ebe7ecf522ae39cad8fa6d2d6eb5a2a6be9299b313e688f57e381`
- `tests/test_client_nep2_vector_wrapper_owner_probe.py`
  - SHA-256 `de581e0a6c526aa6b899123aab209c15d187476f8336b4aa0e2127137dd9c562`

Next step:
- Continue offline/static only.
- Deprioritize isolated NEP2 vector-wrapper clusters unless payload-buffer provenance appears.
- Prioritize TextAsset/LuaScripts payload ownership or protected global-metadata method ownership.

## Round 190 - Client resource surface gap scan imported

Actions:
- Added external `threads/artifacts/round190_client_resource_surface_gap_scan.py` and generated JSON/Markdown evidence.
- Inventoried the installed NSLG client/resource cache in offline static metadata-only mode.
- Imported the scan into qa-agent as raw round133; rebuilt evidence bundle round134 and import queue round135.

Results:
- Total files seen: `677`; safe package/resource files: `556`; aggregate-only runtime files: `76`; sensitive/runtime files skipped: `45`.
- Safe `.ns` bundles: `369`; total `.ns` bytes: `7197259176`.
- High-value resource groups include `luascripts.ns`, `building.ns`, `mapres.ns`, `sprite.ns`, `sharedassets.ns`, `ui`, `terrain`, and `cardmodels`.
- `decoded_game_knowledge_recovered=false`; `safe_for_publish=false`; publishable knowledge entries: `0`.
- Bundle artifacts: `37`; evidence refs: `838`; queue items: `105`.
- Queue target `client_resource_surface_gap_scan_target`: `1`.

Verification:
- External Round190 `py_compile`, `json.tool`, and literal account/password marker scan passed.
- qa-agent targeted py_compile and targeted unittest passed: `6` tests.
- qa-agent full unittest passed: `257` tests. Existing ResourceWarning from `test_lineup_frame_extractor.py` remains non-failing.
- YAML load check passed for round133/134/135.
- Sensitive scan found no literal account/password values in touched source/test/YAML outputs.

Artifacts:
- `threads/artifacts/round190_client_resource_surface_gap_scan.py`
- `threads/artifacts/client_resource_surface_gap_scan_round190.json`
- `threads/artifacts/client_resource_surface_gap_scan_round190.md`
- `packages/qa-agent/ingestion/raw/client_packages/nslg-client-resource-surface-gap-scan-round133.yaml`
- `packages/qa-agent/ingestion/raw/client_packages/nslg-client-evidence-bundle-round134.yaml`
- `packages/qa-agent/ingestion/raw/client_packages/nslg-client-import-queue-round135.yaml`

Hashes:
- `round190_client_resource_surface_gap_scan.py`
  - SHA-256 `d8196c878966ad27e456777c321565b494f847489c2471bd41f2204d8f468cc5`
- `client_resource_surface_gap_scan_round190.json`
  - SHA-256 `d018fabe4e10c2f55b2c22cd5b8b1d65f17901f78e4f0290bc2c640a8efe8bc8`
- `client_resource_surface_gap_scan_round190.md`
  - SHA-256 `7d3ef25edc9f751b2a1b24086e2fa4f70c45529ca866d010a3114558a0d450a9`
- `nslg-client-resource-surface-gap-scan-round133.yaml`
  - SHA-256 `6612e57e5ff7255da5ee6d4dd5167a00458dfd8ff6d6d379d9dac1e411644223`
- `nslg-client-evidence-bundle-round134.yaml`
  - SHA-256 `f3fa29f2b1741ca8ab09bd286af0c4515af2e78930337fcf99c489933d26110e`
- `nslg-client-import-queue-round135.yaml`
  - SHA-256 `749fd2b068d6c964b6d3531d8f9cd46dda31bff9a2e74d3a9baca10120fcba53`

Next:
- Continue offline/static only.
- Build a sanitized `.ns` bundle index/format classifier for `LocalPersistentData/assets/bundles`.
- Prioritize `luascripts.ns`, `building.ns`, `mapres.ns`, `sprite.ns`, and `sharedassets.ns`; do not read account DB/log/session content.


## Round 191 - NS bundle format index imported

Actions:
- Added external 	hreads/artifacts/round191_ns_bundle_format_index.py and generated JSON/Markdown evidence.
- Built a sanitized .ns UnityFS/CAB format index for LocalPersistentData/assets/bundles without exporting payload bytes or reading account DB/log/session/protocol data.
- Imported the index into qa-agent as 
slg-ns-bundle-format-index-round136.yaml.
- Rebuilt evidence bundle/import queue as round137/round138.

Results:
- Bundles indexed: 369.
- UnityFS parse OK: 369; block-info parse OK: 369.
- First data block decompress OK: 369; SerializedFile header parse OK: 369.
- Protected SerializedFile metadata: 369.
- CAB-only bundles: 63; CAB+resS bundles: 306.
- Bundle artifacts: 38; evidence refs: 1071; queue items: 106.
- Queue target 
s_bundle_format_index_target: 1.
- safe_for_publish=false; this is protected metadata decoder-target evidence, not publishable gameplay knowledge.

Verification:
- External Round191 py_compile, json.tool, and literal account/password marker scan passed.
- qa-agent targeted py_compile passed for new/updated format-index/bundle/queue modules and tests.
- qa-agent targeted unittest passed: 8 tests.
- qa-agent full unittest passed: 259 tests. Existing ResourceWarning from 	est_lineup_frame_extractor.py remains non-failing.
- YAML load check passed for round136/137/138.
- Sensitive scan found no literal account/password values in touched source/test/YAML outputs.

Artifacts:
- ingestion/raw/client_packages/nslg-ns-bundle-format-index-round136.yaml
- ingestion/raw/client_packages/nslg-client-evidence-bundle-round137.yaml
- ingestion/raw/client_packages/nslg-client-import-queue-round138.yaml
- src/qa_agent/ingestion/client_ns_bundle_format_index.py
- src/qa_agent/app/summarize_ns_bundle_format_index.py
- 	ests/test_client_ns_bundle_format_index.py

Hashes:
- 
slg-ns-bundle-format-index-round136.yaml
  - SHA-256 d50998f43a913518a222dc2eb690b6cbd7e786a9ce5efbae98edd38c2d9e92d4
- 
slg-client-evidence-bundle-round137.yaml
  - SHA-256 7555a112516f05c02848a783d32b467c91e32f6127ca806c258d94f1d3704a9e
- 
slg-client-import-queue-round138.yaml
  - SHA-256 4f2670f985162c207b73de939432fa4a1953edb473b2b4f9acc58b39bdd9ab1
- src/qa_agent/ingestion/client_ns_bundle_format_index.py
  - SHA-256 1fd6b54420ac554fd11775bac2714bb20b8b1ce72c019c919070c5d78a16d498
- src/qa_agent/app/summarize_ns_bundle_format_index.py
  - SHA-256 4a94e9bb1018840da46c2a4503cc55e516e19e66c36d2c89d725654a3ca34a1
- 	ests/test_client_ns_bundle_format_index.py
  - SHA-256 9a746c92b883a69bde801a82240d8674d70d51bf7ef76935ba3b47e51983a684

Next:
- Continue offline/static only.
- Use the .ns format index to target protected SerializedFile metadata transform recovery.
- Prioritize luascripts.ns, building.ns, mapres.ns, UI, terrain/map resources, and resource-family extraction routes.

## Round 191 closure - NSLG reverse line paused

Decision:
- Pause NSLG client reverse-engineering as the default mainline. The work produced useful offline evidence infrastructure and a resource map, but the ROI is now too low to keep spending high-token exploration cycles.

What was achieved:
- Offline/static guardrails and state tracking are established.
- qa-agent has 38 client evidence artifacts, 1071 evidence refs, and 106 import queue items.
- Round190 inventoried 677 client/resource files, including 556 safe resource files and 369 `.ns` bundles totaling about 7.20 GB.
- Round191 indexed all 369 `.ns` bundles: UnityFS headers, block-info, first block decompress, and SerializedFile headers all parse; all 369 still have protected metadata.
- Negative evidence narrowed several routes: UnityPlayer parser path, NEP2 vector/helper path, GameAssembly registration/initializer/function-pointer paths, and global-metadata string-ref paths.
- qa-agent remained healthy; latest recorded full test run passed 259 tests.

What was not achieved:
- LuaScripts plaintext was not recovered.
- Protected SerializedFile metadata transform was not recovered.
- Normalized decoded hero staging is not reviewed knowledge and must not be published.
- Publishable gameplay knowledge entries remain 0.
- The line does not currently produce commercial MVP user value.

Default next:
- Do not continue this reverse-engineering loop by default.
- Resume only if the user explicitly approves a small capped phase with a concrete failure condition, limited to protected SerializedFile metadata transform recovery.
- Move default engineering focus back to screenshot Advisor, golden replay expansion, low-risk verifier specs, and public/video/manual reviewed qa-agent knowledge.
