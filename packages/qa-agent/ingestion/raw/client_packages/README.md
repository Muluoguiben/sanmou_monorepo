# NSLG Client Package Ingestion

This directory stores sanitized, offline evidence inventories for the local NSLG client package.

## Current Artifacts

- `nslg-client-import-queue-round135.yaml`
  - Source: review/decoder queue rebuilt on top of the round134 evidence bundle and Round190 client resource-surface gap scan.
  - Scope: 105 queue items: the previous 104 review/decoder/static-route items plus 1 resource-surface `.ns` bundle index target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; Round190 shows the installed client has a large resource-cache bundle surface under `LocalPersistentData/assets/bundles`, including `luascripts.ns`, `building.ns`, `mapres.ns`, `sprite.ns`, and related `.ns` families.

- `nslg-client-evidence-bundle-round134.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including Round190 client resource-surface gap scan.
  - Scope: 37 artifacts, 838 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, binary-route artifacts remain decoder targets or negative route closures, and the `.ns` resource surface is inventoried but not decoded.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, and resource-cache bundle extraction planning.

- `nslg-client-resource-surface-gap-scan-round133.yaml`
  - Source: sanitized summary over external Round190 static client install/resource-cache inventory.
  - Scope: 677 files seen; 556 safe package/resource files; 369 safe `.ns` bundles totaling 7,197,259,176 bytes; 76 aggregate-only runtime files; 45 sensitive/runtime files skipped.
  - Current finding: all safe `.ns` resource bundles are under `LocalPersistentData/assets/bundles`; high-value groups include `luascripts.ns`, `building.ns`, `mapres.ns`, `sprite.ns`, `sharedassets.ns`, `ui`, `terrain`, and `cardmodels`.
  - Readiness: `safe_for_publish=false`; this is resource inventory and magic-sample routing evidence, not decoded gameplay knowledge.
  - Use: build a sanitized `.ns` bundle index/format classifier before attempting resource or LuaScripts payload decoding.

- `nslg-client-import-queue-round129.yaml`
  - Source: review/decoder queue rebuilt on top of the round128 evidence bundle and Round188 GameAssembly global-metadata owner probe.
  - Scope: 103 queue items: the previous 102 review/decoder/static-route items plus 1 GameAssembly global-metadata owner route-closure target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; Round188 closes the known `global-metadata.dat` string-ref functions as string-only route evidence, not loader ownership.

- `nslg-client-evidence-bundle-round128.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly global-metadata owner probe through external Round188.
  - Scope: 35 artifacts, 672 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, and current protected metadata ownership blockers.

- `nslg-gameassembly-global-metadata-owner-probe-round127.yaml`
  - Source: sanitized summary over external Round188 GameAssembly `global-metadata.dat` string-ref owner probe.
  - Scope: 2 seed functions inspected: `0x55f6d0` and `0x5736d0`; 2 metadata string-ref functions, 0 file/mapping API functions, 0 MetadataRegistration candidate-ref functions, and 0 loader owner candidates.
  - Current finding: the known `global-metadata.dat` string refs are confirmed, but they do not combine file/mapping APIs with MetadataRegistration candidate ownership.
  - Negative evidence: protected metadata owner, readable metadata, `InitLuaEnv` method pointer, and LuaScripts decoder remain unresolved.
  - Readiness: `safe_for_publish=false`; this is IL2CPP routing evidence, not decoded gameplay knowledge.
  - Use: stop promoting global-metadata string refs alone as loader ownership; continue with protected metadata method-definition recovery or a proven file-buffer owner.

- `nslg-client-import-queue-round120.yaml`
  - Source: review/decoder queue rebuilt on top of the round119 evidence bundle and Round185 GameAssembly MetadataRegistration candidate taxonomy.
  - Scope: 100 queue items: the previous 99 review/decoder/static-route items plus 1 GameAssembly MetadataRegistration candidate-taxonomy target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; Round185 demotes the Round181/182 exact-ref MetadataRegistration-like candidates as tiny-count family evidence and keeps protected metadata method-definition ownership unresolved.

- `nslg-client-evidence-bundle-round119.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly MetadataRegistration candidate taxonomy through external round185.
  - Scope: 32 artifacts; client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, and the current MetadataRegistration candidate taxonomy.

- `nslg-gameassembly-metadata-registration-candidate-taxonomy-round118.yaml`
  - Source: sanitized summary over external Round185 GameAssembly `.rdata` MetadataRegistration-like candidate taxonomy.
  - Scope: 58,879 candidate windows scanned; 12 exact-ref candidates, 0 exact-ref non-tiny candidates, exact-ref max count 15, 182 high-count candidates, and 0 referenced high-count candidates.
  - Current finding: Round182 exact raw refs point to tiny-count candidate-family windows, not a proven MetadataRegistration owner.
  - Negative evidence: high-count windows exist but are unreferenced and weak false-positive-prone scan leads; `InitLuaEnv` method ownership remains unresolved.
  - Readiness: `safe_for_publish=false`; this is IL2CPP routing evidence, not decoded gameplay knowledge.
  - Use: stop promoting Round181/182 top MetadataRegistration-like windows as owner evidence; continue with decoded protected metadata or a proven MetadataRegistration owner/callsite.

- `nslg-client-import-queue-round117.yaml`
  - Source: review/decoder queue rebuilt on top of the round116 evidence bundle and Round184 GameAssembly function-pointer-table probe.
  - Scope: 99 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 TextAsset/xLua boundary ledger method-owner target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 GameAssembly registration pair-context metadata-ownership target, 1 GameAssembly initializer-dispatch indirect-owner target, 1 GameAssembly function-pointer-table known-table route target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round185 MetadataRegistration candidate taxonomy; kept as historical evidence.

- `nslg-client-evidence-bundle-round116.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly function-pointer-table probe evidence through external round184.
  - Scope: 31 artifacts, 622 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: superseded by round119; kept as historical evidence.

- `nslg-gameassembly-function-pointer-table-probe-round115.yaml`
  - Source: sanitized summary over external Round184 GameAssembly `.rdata/.data` function pointer table probe.
  - Scope: 342,009 qword function-pointer hits, 96 known CodeGenModule method tables, 6 known CodeRegistration field arrays, 22 relevant dispatcher pointer hits, 0 dispatcher hits outside known IL2CPP tables, 0 global-metadata string-ref function pointer hits, and 0 independent initializer table candidates.
  - Current finding: dispatcher-shaped functions from Round183 are referenced by known IL2CPP tables: 20 hits in CodeGenModule method pointer tables and 2 hits in CodeRegistration field arrays.
  - Negative evidence: qword-aligned non-exec pointer scanning does not recover `InitLuaEnv` method ownership, a standalone indirect initializer table, or protected metadata method-definition ownership.
  - Readiness: `safe_for_publish=false`; this is IL2CPP routing evidence, not decoded gameplay knowledge.
  - Use: stop treating the Round183 dispatcher pointer hits as initializer ownership; continue with protected metadata method-definition ownership or a more specific metadata-registration bridge.

- `nslg-client-import-queue-round114.yaml`
  - Source: review/decoder queue rebuilt on top of the round113 evidence bundle and Round183 GameAssembly initializer-dispatch trace.
  - Scope: 98 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 TextAsset/xLua boundary ledger method-owner target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 GameAssembly registration pair-context metadata-ownership target, 1 GameAssembly initializer-dispatch indirect-owner target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round184 function-pointer-table probe; kept as historical evidence.

- `nslg-client-evidence-bundle-round113.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly initializer-dispatch trace evidence through external round183.
  - Scope: 30 artifacts, 618 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: superseded by round116; kept as historical evidence.

- `nslg-gameassembly-initializer-dispatch-trace-round112.yaml`
  - Source: sanitized summary over external Round183 GameAssembly bounded initializer-dispatch trace.
  - Scope: 290,472 `.pdata` function boundaries and 16,265,170 instructions scanned; 0 registration-anchor ref functions, 0 metadata-candidate ref functions, 2 global-metadata string ref functions, 0 non-exec function-pointer hits, and 24 broad dispatcher-shaped candidates.
  - Current finding: direct bounded callgraph paths from entry/export roots to CodeRegistration/MetadataRegistration-like candidates were not recovered; the only concrete string route remains the known global-metadata string refs at `0x55f6d0` and `0x5736d0`.
  - Negative evidence: bounded direct-call initializer dispatcher tracing does not pair CodeRegistration with MetadataRegistration and does not recover `InitLuaEnv` method ownership.
  - Readiness: `safe_for_publish=false`; this is IL2CPP routing evidence, not decoded gameplay knowledge.
  - Use: stop repeating bounded direct-call dispatcher tracing for this build; continue with protected metadata method-definition ownership or bounded indirect init-table decoding.

- `nslg-client-import-queue-round111.yaml`
  - Source: review/decoder queue rebuilt on top of the round110 evidence bundle and Round182 GameAssembly registration pair-context probe.
  - Scope: 97 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 TextAsset/xLua boundary ledger method-owner target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 GameAssembly registration pair-context metadata-ownership target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round183 initializer-dispatch trace; kept as historical evidence.

- `nslg-client-evidence-bundle-round110.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly registration pair-context evidence through external round182.
  - Scope: 29 artifacts, 613 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: superseded by round113; kept as historical evidence.

- `nslg-gameassembly-registration-pair-context-probe-round109.yaml`
  - Source: sanitized summary over external Round182 GameAssembly CodeRegistration/MetadataRegistration pair-context probe.
  - Scope: 10 registration targets, 12 metadata-like targets, 7 raw registration refs, 0 raw refs to the CodeRegistration start, 25 raw metadata-candidate refs, 0 registration code refs, 0 metadata-candidate code refs, 0 paired pointer neighborhoods, and 0 call-argument pair windows.
  - Current finding: top MetadataRegistration-like candidates have exact raw references clustered in `.data`/`.rdata`, which is useful as a candidate-family map but not as ownership proof.
  - Negative evidence: direct pointer-pair recovery is negative in this build: no exact raw reference to the CodeRegistration start, no static code refs to either side, no paired pointer neighborhood, and no call-argument window.
  - Readiness: `safe_for_publish=false`; this is IL2CPP registration route-closure evidence, not decoded gameplay knowledge.
  - Use: stop repeating direct pointer-pair xref scans; pivot to decoded protected metadata method-definition ownership or a broader bounded IL2CPP initializer dispatcher trace.

- `nslg-client-import-queue-round108.yaml`
  - Source: review/decoder queue rebuilt on top of the round107 evidence bundle and Round181 GameAssembly registration-layout probe.
  - Scope: 97 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 TextAsset/xLua boundary ledger method-owner target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 GameAssembly registration-layout MetadataRegistration pairing target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round182 registration pair-context probe; kept as historical evidence.

- `nslg-client-evidence-bundle-round107.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly CodeRegistration layout evidence through external round181.
  - Scope: 28 artifacts, 609 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: superseded by round110; kept as historical evidence.

- `nslg-gameassembly-registration-layout-probe-round106.yaml`
  - Source: sanitized summary over external Round181 GameAssembly CodeRegistration layout probe.
  - Scope: 1 CodeRegistration start candidate, primary start `0x4332730`, 6 count/pointer pairs, 9 pointer-only fields, CodeGenModules count/pointer at `+0x78/+0x80`, 0 code refs, 7 raw VA refs, and 58,746 weak MetadataRegistration-like candidate windows.
  - Current finding: Round180's earlier `0x4332718` owner inference is corrected; the stronger CodeRegistration-like layout anchor starts at `0x4332730`, with CodeGenModules count `98` and array `0x50a2840`.
  - Negative evidence: no registration callsite or MetadataRegistration pairing was recovered; MetadataRegistration-like windows remain weak/unpaired candidates, so method-index to pointer mapping and `InitLuaEnv` ownership remain unresolved.
  - Readiness: `safe_for_publish=false`; this is IL2CPP registration routing evidence, not decoded gameplay knowledge.
  - Use: superseded by Round182 registration pair-context probe; kept as historical evidence.

- `nslg-client-import-queue-round105.yaml`
  - Source: review/decoder queue rebuilt on top of the round104 evidence bundle and Round180 GameAssembly registration-anchor probe.
  - Scope: 97 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 TextAsset/xLua boundary ledger method-owner target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 GameAssembly registration-anchor MetadataRegistration pairing target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round181 registration-layout probe; kept as historical evidence.

- `nslg-client-evidence-bundle-round104.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly CodeRegistration/CodeGenModules anchor evidence through external round180.
  - Scope: 27 artifacts, 605 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: superseded by round107; kept as historical evidence.

- `nslg-gameassembly-registration-anchor-probe-round103.yaml`
  - Source: sanitized summary over external Round180 GameAssembly CodeRegistration-side CodeGenModules anchor probe.
  - Scope: 1 CodeGenModules field candidate, 98 declared CodeGenModules, 98 parsed modules, 96 nonzero method modules, Assembly-CSharp module index `5`, and 30,078 Assembly-CSharp method pointers.
  - Current finding: a CodeRegistration-style count/pointer field neighborhood anchors the full CodeGenModules array at `0x50a2840`; Assembly-CSharp is index `5` with method pointer table `0x50b9840`.
  - Negative evidence: no registration callsite or MetadataRegistration pairing was recovered, so method-index to pointer mapping and `InitLuaEnv` ownership remain unresolved.
  - Readiness: `safe_for_publish=false`; this is IL2CPP registration routing evidence, not decoded gameplay knowledge.
  - Use: superseded by Round181 registration-layout probe; kept as historical evidence.

- `nslg-gameassembly-codegen-module-probe-round100.yaml`
  - Source: sanitized summary over external Round179 GameAssembly IL2CPP CodeGenModule probe.
  - Scope: 95 CodeGenModule-like candidates, 4 contiguous module-pointer runs, largest run of 49 modules, 2 Assembly-CSharp modules, 30,078 Assembly-CSharp method pointers, 29,351 executable method pointers, and 727 null method pointers.
  - Current finding: GameAssembly contains CodeGenModule-like records for `Assembly-CSharp.dll` and `Assembly-CSharp-firstpass.dll`, including dense method pointer tables in executable sections.
  - Negative evidence: the probe does not recover `InitLuaEnv` method ownership or protected metadata names; method pointer tables are registration-side anchors only.
  - Readiness: `safe_for_publish=false`; this is IL2CPP registration routing evidence, not decoded gameplay knowledge.
  - Use: superseded by Round180 registration-anchor probe for active queue planning; keep as module-table evidence.

- `nslg-runtime-init-registry-probe-round97.yaml`
  - Source: sanitized summary over external Round178 RuntimeInitializeOnLoads registry probe.
  - Scope: 12 runtime-initialize entries, 1 `NSLGame.Patcher.GameUpdater.InitLuaEnv` entry, 0 native address/token fields, 5 present module records, and 1 UnityPlayer static code reference to the registry filename.
  - Current finding: `RuntimeInitializeOnLoads.json` is present and declares `InitLuaEnv`, but the registry stores managed names/loadTypes only and does not expose the native method address or IL2CPP token ownership.
  - Negative evidence: `InitLuaEnv`, `GameUpdater`, and `NSLGame.Patcher` strings are absent from GameAssembly, NEP2, xlua, and protected global-metadata; this closes the direct registry-to-native-address route.
  - Readiness: `safe_for_publish=false`; this is runtime-init routing evidence, not decoded gameplay knowledge.
  - Use: superseded by Round180 registration anchors for active queue planning; keep as managed-name evidence for `InitLuaEnv`.

- `nslg-client-import-queue-round102.yaml`
  - Source: review/decoder queue rebuilt on top of the round101 evidence bundle and Round179 GameAssembly IL2CPP CodeGenModule probe.
  - Scope: 97 queue items.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round180 registration-anchor probe; kept as historical evidence.

- `nslg-client-evidence-bundle-round101.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, including GameAssembly CodeGenModule registration evidence through external round179.
  - Scope: 26 artifacts, 602 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`.
  - Use: superseded by round104; kept as historical evidence.

- `nslg-client-import-queue-round99.yaml`
  - Source: review/decoder queue rebuilt on top of the round98 evidence bundle and Round178 RuntimeInitializeOnLoads registry probe.
  - Scope: 97 queue items.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round179 CodeGenModule probe; kept as historical evidence.

- `nslg-client-evidence-bundle-round98.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, including RuntimeInitializeOnLoads registry evidence through external round178.
  - Scope: 25 artifacts, 598 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`.
  - Use: superseded by round101; kept as historical evidence.

- `nslg-client-import-queue-round96.yaml`
  - Source: review/decoder queue rebuilt on top of the round95 evidence bundle and Round177 TextAsset/xLua boundary ledger.
  - Scope: 97 queue items.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round178 registry probe; kept as historical evidence.

- `nslg-client-evidence-bundle-round95.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including TextAsset/xLua boundary ledger evidence through external round177.
  - Scope: 24 artifacts, 594 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: superseded by round98; kept as historical evidence.

- `nslg-textasset-xlua-boundary-ledger-round94.yaml`
  - Source: sanitized summary over external Round177 TextAsset/xLua boundary route ledger.
  - Scope: 6 route records: 4 closed negative routes, 1 blocked pending metadata route, and 1 next viable route.
  - Current finding: GameAssembly static TextAsset/loadbuffer correlation, native import/export boundary tracing, direct 0x5ccc30 resolver callers, and resolved-payload exact native anchors do not prove a native TextAsset script-buffer owner or LuaScripts decoder.
  - Negative evidence: 0 proven payload-owner routes, 0 exact strong native anchor hits, and 0 resolver caller payload-owner candidates.
  - Readiness: `safe_for_publish=false`; this is route-ledger/negative planning evidence, not decoded gameplay knowledge.
  - Use: stop repeating broad native strings or embedded-constant scans; move to protected metadata/method ownership recovery or narrow control-flow only after owner evidence appears.

- `nslg-client-import-queue-round93.yaml`
  - Source: review/decoder queue rebuilt on top of the round92 evidence bundle and Round176 resolved-payload native anchor scan.
  - Scope: 97 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 resolved-payload native-anchor boundary trace target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by Round177 boundary ledger; kept as historical evidence.

- `nslg-client-evidence-bundle-round92.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including resolved-payload native-anchor scan evidence through external round176.
  - Scope: 23 artifacts, 588 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: superseded by round95; kept as historical evidence.

- `nslg-resolved-payload-native-anchor-scan-round91.yaml`
  - Source: sanitized summary over external Round176 resolved-payload native-anchor scan.
  - Scope: 368 anchors over 4 native modules: path IDs, object offsets, payload offsets, script lengths, first/last payload blocks, and payload hashes from the resolved LuaScripts corpus.
  - Current finding: CAB control anchors are valid, but `GameAssembly.dll`, `NEP2.dll`, `UnityPlayer.dll`, and `xlua.dll` contain 0 strong native anchor hits and 0 strong co-occurrence windows; isolated 4-byte numeric hits remain weak noise.
  - Negative evidence: exact path_id/payload-block/hash constants are not statically embedded in native modules, so this route does not prove native payload-buffer ownership or a LuaScripts decoder.
  - Readiness: `safe_for_publish=false`; this is route/negative evidence, not decoded gameplay knowledge.
  - Use: stop searching native binaries for embedded resolved payload constants and move to boundary-focused control-flow/method ownership analysis.

- `nslg-client-import-queue-round90.yaml`
  - Source: review/decoder queue rebuilt on top of the round89 evidence bundle and Round175 SerializedFile TextAsset path_id/object_offset resolution.
  - Scope: 97 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 Serialized TextAsset path-resolution target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; the Round174 SerializedFile object-layout target is superseded by the stronger Round175 path_id/object_offset resolution target.

- `nslg-client-evidence-bundle-round89.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including SerializedFile TextAsset path-resolution evidence through external round175.
  - Scope: 22 artifacts, 584 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, payload corpus eval data, TextAsset owner negative evidence, SerializedFile object-layout constraints, path_id/object_offset anchors, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, global-metadata transform/loader evidence, NEP2 owner scans, resolver evidence, and next actions.

- `nslg-serialized-textasset-path-resolution-round88.yaml`
  - Source: sanitized summary over external Round175 SerializedFile TextAsset path_id/object_offset resolution probe.
  - Scope: 104 relevant path records, 104 verified AssetBundle container records, 104 resolved path_id/object_offset mappings, 16 unique resolved object offsets, 16 unique payload hashes, and 23 scenarios.
  - Current finding: all LuaScripts path records now resolve to one exact TextAsset object offset by verified container record plus catalog payload sha1 plus Round174 object layout.
  - Negative evidence: native payload-buffer ownership is still unproven, the Lua payload decoder is still unrecovered, and encrypted SerializedFile metadata object table is not independently decrypted.
  - Readiness: `safe_for_publish=false`; this is path-resolution/decoder-route evidence, not decoded gameplay knowledge.
  - Use: use exact path_id/object_offset/payload_offset/script_len anchors to validate future decoder candidates and stop broad TextAsset string scans.

- `nslg-client-import-queue-round87.yaml`
  - Source: review/decoder queue rebuilt on top of the round86 evidence bundle and Round174 SerializedFile TextAsset layout probe.
  - Scope: 97 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 Serialized TextAsset layout target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; the Round173 TextAsset native string target is superseded by the stronger Round174 SerializedFile object-layout target.

- `nslg-client-evidence-bundle-round86.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including SerializedFile TextAsset object-layout evidence through external round174.
  - Scope: 21 artifacts, 480 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, payload corpus eval data, TextAsset owner negative evidence, SerializedFile object-layout constraints, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, global-metadata transform/loader evidence, NEP2 owner scans, resolver evidence, and next actions.

- `nslg-serialized-textasset-layout-round85.yaml`
  - Source: sanitized summary over external Round174 SerializedFile TextAsset object-layout probe.
  - Scope: 104 relevant path records, 932 TextAsset object matches, 52 unique object offsets, 52 unique payload hashes, and 16 stems.
  - Current finding: all 932 matches validate the serialized `m_Name -> aligned script_len -> payload bytes` layout; payload offsets and lengths are now concrete static constraints for future decoder candidates.
  - Negative evidence: path_id to exact object_offset is still unresolved, native payload-buffer ownership is still unproven, and Lua payloads remain encrypted.
  - Readiness: `safe_for_publish=false`; this is layout/decoder-route evidence, not decoded gameplay knowledge.
  - Use: parse SerializedFile object/preload/container tables next to resolve each AssetBundle path_id to one exact TextAsset object offset.

- `nslg-client-import-queue-round84.yaml`
  - Source: review/decoder queue rebuilt on top of the round83 evidence bundle and Round173 TextAsset payload-owner trace.
  - Scope: 97 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 1 TextAsset payload-owner trace target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; Round173 keeps TextAsset native string evidence as static route evidence only and points the next useful work toward SerializedFile object layout or managed metadata recovery.

- `nslg-client-evidence-bundle-round83.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including TextAsset payload-owner trace evidence through external round173.
  - Scope: 20 artifacts, 464 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, payload corpus eval data, TextAsset owner negative evidence, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, global-metadata transform/loader evidence, NEP2 owner scans, resolver evidence, and next actions.

- `nslg-textasset-payload-owner-trace-round82.yaml`
  - Source: sanitized summary over external Round173 TextAsset/LuaScripts payload owner static trace.
  - Scope: 4 native modules, 315 conservative TextAsset/LuaScripts/asset terms, and 706 native string hits.
  - Current finding: native modules contain TextAsset/LuaScripts route strings, but no conservative asset path/stem/filename hit and no code owner reference attaches those strings to payload-buffer handling.
  - Negative evidence: 0 exact asset path/stem hits, 0 code refs, 0 candidate functions, 0 payload-owner candidates, 0 recovered Lua payload decoders.
  - Readiness: `safe_for_publish=false`; this is static route/negative evidence, not decoded gameplay knowledge.
  - Use: stop relying on broad native string provenance for this route and shift to SerializedFile object layout or managed metadata recovery to attach payload pointer and length.

- `nslg-client-import-queue-round81.yaml`
  - Source: review/decoder queue rebuilt on top of the round80 evidence bundle and Round172 LuaScripts payload variant corpus probe.
  - Scope: 96 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload variant-corpus target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; the old LuaScripts payload cipher-profile queue item is superseded by the expanded 932-variant corpus target, and the next useful work remains payload-buffer owner tracing rather than static header/IV stripping.

- `nslg-client-evidence-bundle-round80.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including LuaScripts payload variant-corpus evidence through external round172.
  - Scope: 19 artifacts, 463 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, payload corpus eval data, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, global-metadata transform/loader evidence, NEP2 read/mapping owner closure, NEP2 InitLuaScriptsScan data-owner route evidence, resolver evidence, and next actions.

- `nslg-luascripts-payload-variant-corpus-round79.yaml`
  - Source: sanitized summary over external Round172 LuaScripts TextAsset payload variant corpus probe.
  - Scope: 104 relevant TextAsset records, 932 payload variants, 16 stems, 23 scenarios, 52 unique ciphertext hashes, and 40 duplicate ciphertext groups.
  - Current finding: expanded corpus gives reusable decoder/eval material across repeated scenario variants; all payload sizes are 16-byte aligned and duplicate encrypted payload groups are visible across repeated asset references.
  - Negative evidence: no tested offset skip exposed Lua bytecode/source terms, high-printable plaintext, or zlib/gzip/lzma/bz2 payloads; simple header/IV stripping is not a useful static route.
  - Readiness: `safe_for_publish=false`; this is encrypted payload corpus evidence, not decoded metadata or gameplay knowledge.
  - Use: stop spending effort on offset-skip plaintext/decompression probes and use the 932-variant corpus to validate any future native decoder candidate.

- `nslg-client-import-queue-round78.yaml`
  - Source: review/decoder queue rebuilt on top of the round77 evidence bundle and Round171 NEP2 InitLuaScriptsScan / CGameProtector data-reference owner scan.
  - Scope: 96 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 NEP2 InitLuaScriptsScan data-owner scan target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; the old generic read/mapping owner target is superseded by the Round171 InitLuaScriptsScan / CGameProtector data-reference route evidence.

- `nslg-client-evidence-bundle-round77.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including NEP2 InitLuaScriptsScan / CGameProtector data-owner scan evidence through external round171.
  - Scope: 18 artifacts, 447 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, global-metadata transform/loader evidence, NEP2 read/mapping owner closure, NEP2 InitLuaScriptsScan data-owner route evidence, resolver evidence, and next actions.

- `nslg-nep2-init-data-owner-scan-round76.yaml`
  - Source: sanitized summary over external Round171 NEP2 InitLuaScriptsScan / CGameProtector data-reference owner scan.
  - Scope: 90 focus targets, 255 data references, 4 bridge record windows, 2 bridge windows with code pointers, and 13 inspected functions.
  - Current finding: InitLuaScriptsScan / CGameProtector RTTI and bridge windows resolve to metadata/lambda support pointers plus EH/FH4 data refs, but no inspected data-record consumer proves payload-buffer ownership.
  - Negative evidence: 0 data-reference owner functions, 0 payload owner candidates, 0 file-buffer owners, 0 recovered Lua payload decoders, and 0 recovered plaintext metadata loaders.
  - Readiness: `safe_for_publish=false`; this is decoder-planning route evidence, not decoded metadata or gameplay knowledge.
  - Use: avoid treating bridge metadata or data records as decoder proof unless a later slice attaches payload-buffer provenance.

- `nslg-client-import-queue-round75.yaml`
  - Source: review/decoder queue rebuilt on top of the round74 evidence bundle and Round170 NEP2 read/mapping owner scan.
  - Scope: 96 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 NEP2 read/mapping owner scan target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue; the old `nep2_metadata_loader_deep_slice_target` is superseded by the Round170 owner scan, so the next metadata-loader route is NEP2 InitLuaScriptsScan / CGameProtector data-reference ownership rather than generic file IO.

- `nslg-client-evidence-bundle-round74.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including NEP2 read/mapping owner scan evidence through external round170.
  - Scope: 17 artifacts, 433 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and binary-route artifacts remain decoder targets or negative route closures.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, global-metadata transform/loader evidence, NEP2 read/mapping owner closure, resolver evidence, and next actions.

- `nslg-nep2-read-mapping-owner-scan-round73.yaml`
  - Source: sanitized summary over external Round170 NEP2 actual read/mapping import-owner scan.
  - Scope: 2 owner functions; both are `GetFileSize` / `GetFileSizeEx` owners only.
  - Current finding: no static owner was found for `ReadFile`, `MapViewOfFile`, `CreateFileMapping`, or `SetFilePointer`; the two actual file-size owners are `0xd720` and `0xd7c0`.
  - Negative evidence: neither owner has `global-metadata.dat`, `LuaScripts`, `InitLuaScriptsScan`, protected +8 payload, or metadata wrapper provenance in the bounded caller/callee neighborhood.
  - Readiness: `safe_for_publish=false`; this is negative decoder-planning evidence, not decoded metadata or gameplay knowledge.
  - Use: demote generic NEP2 file IO as a metadata-loader route and pivot to InitLuaScriptsScan / CGameProtector data-reference ownership.

- `nslg-nep2-global-metadata-loader-deep-slice-round70.yaml`
  - Source: sanitized summary over external Round169 NEP2 `0xd410` / `0xd870` global-metadata loader candidate deep-slice.
  - Scope: 2 target functions; both closed as metadata-loader candidates.
  - Current finding: `0xd410` resolves as a recursive directory-size walker using `FindFirstFileW` / `FindNextFileW` / `FindClose`; `0xd870` resolves as a file-status/open helper using `GetFileAttributesW`, `GetLastError`, `CreateFileW`, `FindFirstFileW`, `FindClose`, and `CloseHandle`.
  - Negative evidence: neither target calls `ReadFile`, `MapViewOfFile`, or `GetFileSize`, references `global-metadata` strings/constants, or proves ownership of the protected +8 metadata payload buffer.
  - Readiness: `safe_for_publish=false`; this is negative decoder-planning evidence, not decoded metadata or gameplay knowledge.
  - Use: demote `0xd410` / `0xd870` and pivot to actual NEP2 ReadFile/MapViewOfFile owners or InitLuaScriptsScan file-buffer provenance.

- `nslg-client-import-queue-round69.yaml`
  - Source: review/decoder queue rebuilt on top of the round68 evidence bundle.
  - Scope: 96 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 global metadata loader mutation scan target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder boundary tracing, global-metadata loader mutation deep-slicing, resolver caller negative evidence, method ownership blockers, evidence refs, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round68.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including global-metadata loader-mutation scan evidence through external round168.
  - Scope: 15 artifacts, 427 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and all binary-route artifacts remain decoder targets.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, global-metadata transform negative evidence, global-metadata loader mutation scan evidence, resolver descriptor evidence, resolver caller negative evidence, and next actions.

- `nslg-global-metadata-loader-scan-round67.yaml`
  - Source: sanitized summary over external Round168 `global-metadata.dat` loader-mutation static scan.
  - Scope: 4 binaries, 554 function candidates, 0 full loader-mutation gate candidates, 2 file API + 16-byte/loop route candidates, and 0 metadata-reference candidates.
  - Current finding: top file+16 route candidates are `NEP2.dll` functions `0xd410` and `0xd870`, but neither has read/mapping provenance or metadata wrapper/string evidence; no inspected function combines file/mapping API provenance, metadata wrapper evidence, +8 payload handling, and 16-byte/loop evidence in one full gate.
  - Readiness: `safe_for_publish=false`; this is static decoder-planning evidence, not decoded metadata or gameplay knowledge.
  - Use: deep-slice the top NEP2 file+16 candidates for global-metadata path construction, file-buffer ownership, and +8 payload pointer handoff before promoting any loader-mutation route.

- `nslg-client-import-queue-round66.yaml`
  - Source: review/decoder queue rebuilt on top of the round65 evidence bundle.
  - Scope: 95 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 global metadata transform probe target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder boundary tracing, global-metadata loader mutation routing, resolver caller negative evidence, method ownership blockers, evidence refs, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round65.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including global-metadata transform-probe negative evidence through external round167.
  - Scope: 14 artifacts, 424 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and all binary-route artifacts remain decoder targets.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, global-metadata transform negative evidence, resolver descriptor evidence, resolver caller negative evidence, and next actions.

- `nslg-global-metadata-transform-probe-round64.yaml`
  - Source: sanitized summary over external Round167 protected `global-metadata.dat` transform probe.
  - Scope: 1314 bounded transform candidates over the protected payload, 0 known metadata plaintext hits, and repeated 8/16/32-byte block statistics.
  - Current finding: the wrapper remains `magic + file_size + protected_payload`; single-byte xor/add/sub, byte rotations, nibble swap, dword byte-swap, simple 4-byte repeating xor, and small dword add/sub transforms did not recover a plausible IL2CPP header or `Assembly-CSharp` / `NSLGame` strings.
  - Readiness: `safe_for_publish=false`; this is negative decoder-planning evidence, not game knowledge.
  - Use: stop treating file-only simple transforms as a likely path; pivot to the loader mutation point that consumes `global-metadata.dat` +8 payload bytes.

- `nslg-client-import-queue-round63.yaml`
  - Source: review/decoder queue rebuilt on top of the round62 evidence bundle.
  - Scope: 94 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, 1 GameAssembly resolver trace target, and 1 GameAssembly resolver caller trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder boundary tracing, resolver caller negative evidence, method ownership blockers, evidence refs, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round62.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly resolver caller payload-owner negative evidence through external round166.
  - Scope: 13 artifacts, 421 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and all binary-route artifacts remain decoder targets.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, resolver descriptor evidence, resolver caller negative evidence, and next actions.

- `nslg-gameassembly-resolver-caller-trace-round61.yaml`
  - Source: sanitized summary over external Round166 GameAssembly direct-caller payload-owner trace for resolver candidate `0x5ccc30`.
  - Scope: all 2870 unique direct caller functions to `0x5ccc30`, covering 2948 direct rel32 callsites.
  - Current finding: 150 direct callers are xLua/lua API descriptor-only shapes; 0 direct callers reference TextAsset labels, LuaScripts/data stems, or satisfy the payload-owner candidate gate.
  - Readiness: `safe_for_publish=false`; this is negative decoder-planning evidence, not game knowledge.
  - Use: stop treating the direct `0x5ccc30` caller layer as a payload-owner lead unless metadata recovery or a separate owner trace adds TextAsset/file-buffer provenance.

- `nslg-client-import-queue-round60.yaml`
  - Source: review/decoder queue rebuilt on top of the round59 evidence bundle.
  - Scope: 93 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 native loadbuffer boundary trace target, 1 runtime init metadata route target, and 1 GameAssembly resolver trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder boundary tracing, resolver/method ownership blockers, evidence refs, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round59.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly resolver candidate evidence through external round165.
  - Scope: 12 artifacts, 418 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and all binary-route artifacts remain decoder targets.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, resolver descriptor evidence, and next actions.

- `nslg-gameassembly-resolver-trace-round58.yaml`
  - Source: sanitized summary over external Round165 GameAssembly resolver candidate trace for `0x5ccc30`.
  - Scope: 2948 direct rel32 callsites to `0x5ccc30`, 240 sampled direct caller functions, and 28 sampled caller functions with xLua/TextAsset/LuaScripts-related string references.
  - Current finding: `0x5ccc30` is supported as an xLua API descriptor/internal resolver route, but the candidate itself does not prove `InitLuaEnv` method ownership, TextAsset payload-buffer ownership, or a LuaScripts decoder.
  - Readiness: `safe_for_publish=false`; this is decoder-planning evidence, not game knowledge.
  - Use: keep GameAssembly descriptor resolver evidence separate from payload decoder evidence; continue only with protected metadata recovery or caller provenance that proves asset/file-buffer ownership.

- `nslg-client-import-queue-round57.yaml`
  - Source: review/decoder queue rebuilt on top of the round56 evidence bundle.
  - Scope: 92 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, 1 native loadbuffer boundary trace target, and 1 runtime init metadata route target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder boundary tracing, evidence refs, blockers, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round56.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including runtime init metadata route evidence through external round164.
  - Scope: 11 artifacts, 392 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts payloads remain undecoded, and the binary-route artifacts remain decoder targets.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, bridge metadata, payload cipher profile, native boundary evidence, runtime init route evidence, and next actions.

- `nslg-runtime-init-metadata-route-round55.yaml`
  - Source: sanitized summary over external Round164 runtime init / metadata route evidence.
  - Scope: RuntimeInitializeOnLoad `InitLuaEnv` anchor, protected `global-metadata.dat` wrapper evidence, GameAssembly TextAsset/loadbuffer route evidence, NEP2 InitLuaScriptsScan bridge evidence, and native loadbuffer boundary evidence.
  - Current finding: `NSLGame.Patcher.GameUpdater.InitLuaEnv` is known from prior local runtime-init analysis and `global-metadata.dat` is confirmed as a protected wrapper, but the standalone `RuntimeInitializeOnLoads.json` file is not present in this snapshot, protected metadata is not decoded, and the `InitLuaEnv` method address is not recovered.
  - Readiness: `safe_for_publish=false`; this is decoder-planning evidence, not game knowledge.
  - Use: prioritize protected metadata/method ownership recovery before further TextAsset/xLua decoder promotion.

- `nslg-client-import-queue-round54.yaml`
  - Source: review/decoder queue rebuilt on top of the round53 evidence bundle.
  - Scope: 91 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, 1 NEP2 InitLuaScriptsScan bridge trace target, and 1 native loadbuffer boundary trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by round57; retained for audit history.

- `nslg-client-evidence-bundle-round53.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, including native loadbuffer boundary trace evidence through external round163.
  - Scope: 10 artifacts, 387 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; retained for audit history before runtime init route evidence was added.
  - Use: superseded by round56.

- `nslg-native-loadbuffer-boundary-round52.yaml`
  - Source: sanitized summary over external Round163 native loadbuffer boundary trace.
  - Scope: 4 native modules: `GameAssembly.dll`, `NEP2.dll`, `UnityPlayer.dll`, and `xlua.dll`.
  - Current finding: xLua loadbuffer exports are present in the plugin, but `GameAssembly.dll` does not statically import xLua/lua/loadbuffer symbols and no static import/IAT caller or keyword data-ref path proves `TextAsset` bytes flowing into a decoder and then into xLua loadbuffer.
  - Readiness: `safe_for_publish=false`; this is decoder-routing evidence, not game knowledge.
  - Use: treat import/export analysis as negative boundary evidence and continue only with provenance-backed buffer-owner tracing or metadata/runtime-init reconstruction.

- `nslg-client-import-queue-round51.yaml`
  - Source: review/decoder queue rebuilt on top of the round50 evidence bundle.
  - Scope: 90 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 1 LuaScripts payload cipher-profile target, 4 NEP2 static trace targets, 1 GameAssembly static trace target, and 1 NEP2 InitLuaScriptsScan bridge trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: superseded by round54; retained for audit history.

- `nslg-client-evidence-bundle-round50.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, including LuaScripts payload cipher-profile evidence through external round162.
  - Scope: 9 artifacts, 383 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; retained for audit history before native boundary evidence was added.
  - Use: superseded by round53.

- `nslg-luascripts-payload-cipher-profile-round49.yaml`
  - Source: sanitized summary over external Round162 LuaScripts payload cipher profile.
  - Scope: 16 extracted high-value LuaScripts TextAsset payload samples.
  - Current finding: every profiled payload is 16-byte aligned and high-entropy; no cross-file shared 16-byte blocks or duplicate first blocks were found; standard decompression, direct plaintext terms, single-byte XOR, and simple crib-derived repeating XOR did not recover readable payloads.
  - Readiness: `safe_for_publish=false`; this is decoder-routing evidence, not game knowledge.
  - Use: stop low-yield static key/string brute force and prioritize locating the native buffer owner at the `TextAsset bytes -> decoder -> xLua loadbuffer` boundary.

- `nslg-client-import-queue-round48.yaml`
  - Source: review/decoder queue rebuilt on top of the round47 evidence bundle.
  - Scope: 89 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 4 NEP2 static trace targets, 1 GameAssembly static trace target, and 1 NEP2 InitLuaScriptsScan bridge trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder narrowing, bridge evidence refs, blockers, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round47.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including NEP2 InitLuaScriptsScan bridge metadata evidence through external round161.
  - Scope: 8 artifacts, 367 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts/NEP2/GameAssembly artifacts remain decoder targets, NEP2 provenance closures are negative routing evidence, and InitLuaScriptsScan bridge metadata does not prove a payload decoder.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, bridge metadata, and next actions.

- `nslg-nep2-init-bridge-round46.yaml`
  - Source: sanitized summary over external NEP2 InitLuaScriptsScan bridge evidence from rounds 34, 96, 97, 98, 99, and 161.
  - Scope: 4 confirmed InitLuaScriptsScan RTTI/lambda bridge metadata records, 4 bridge code pointers, 2 EH/FH4 range summaries, 4 constructor/enqueue seeds, and 13 candidate function summaries.
  - Current finding: InitLuaScriptsScan CGameProtector bridge metadata is real, but no inspected bridge, seed, or owner candidate proves a LuaScripts payload decoder, file-buffer owner, or CAB/SerializedFile mutating transform.
  - Readiness: `safe_for_publish=false`; this is decoder routing evidence, not game knowledge.
  - Use: keep NEP2 InitLuaScriptsScan as the highest-priority static route while avoiding broad string chasing and shape-only false leads.

- `nslg-client-import-queue-round45.yaml`
  - Source: review/decoder queue rebuilt on top of the round44 evidence bundle.
  - Scope: 88 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, 4 NEP2 static trace targets, and 1 GameAssembly static trace target.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder narrowing, evidence refs, blockers, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round44.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including GameAssembly route trace evidence through round160.
  - Scope: 7 artifacts, 346 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts/NEP2/GameAssembly artifacts remain decoder targets, and NEP2 provenance closures are negative routing evidence.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, and next actions.

- `nslg-gameassembly-route-trace-round43.yaml`
  - Source: sanitized summary over external GameAssembly route trace rounds 42, 71, 105, 123, 124, and 160.
  - Scope: 6 GameAssembly static artifacts, 270 target strings, 15 code refs, 31 function refs.
  - Current finding: `TextAsset::get_bytes` and `xluaL_loadbuffer` names are present, but current static route evidence does not prove a TextAsset/get_bytes -> xluaL_loadbuffer bridge.
  - Readiness: `safe_for_publish=false`; this is decoder routing evidence, not game knowledge.
  - Use: keep GameAssembly as a tracked fallback route while prioritizing NEP2 `InitLuaScriptsScan` or runtime-independent TextAsset payload decoder recovery.

- `nslg-client-import-queue-round42.yaml`
  - Source: review/decoder queue rebuilt on top of the round41 evidence bundle.
  - Scope: 87 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, and 4 NEP2 static trace targets.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder narrowing, evidence refs, blockers, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round41.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including NEP2 provenance closure evidence through round159.
  - Scope: 6 artifacts, 340 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts/NEP2 artifacts remain decoder targets, and NEP2 provenance closures are negative routing evidence.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, and next actions.

- `nslg-nep2-provenance-closures-round40.yaml`
  - Source: sanitized summary over external NEP2 provenance closure rounds 137-159.
  - Scope: 23 closed NEP2 RVA leads, all classified as `closed_no_file_buffer_provenance`.
  - Current finding: bounded caller/callee and pointer-ref provenance found no CAB, SerializedFile, global-metadata, AssetBundle, LuaScripts payload, keyword/import, or file-buffer owner path for these shape-only leads.
  - Latest closed lead: `0x4a471a`.
  - Next lead from the external analysis log: `0x4a28e9`, gated by strict provenance requirements.
  - Use: negative routing evidence to avoid repeating broad shape-only NEP2 scans.

- `nslg-client-import-queue-round39.yaml`
  - Source: review/decoder queue rebuilt on top of the round38 evidence bundle.
  - Scope: 87 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, and 4 NEP2 static trace targets.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: current sorted next-work queue for manual review, decoder narrowing, evidence refs, blockers, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round38.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts, now including NEP2 provenance closure evidence.
  - Scope: 6 artifacts, 339 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, LuaScripts/NEP2 artifacts remain decoder targets, and NEP2 provenance closures are negative routing evidence.
  - Use: latest qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, closed reverse-engineering routes, and next actions.

- `nslg-nep2-provenance-closures-round37.yaml`
  - Source: sanitized summary over external NEP2 provenance closure rounds 137-158.
  - Scope: 22 closed NEP2 RVA leads, all classified as `closed_no_file_buffer_provenance`.
  - Current finding: bounded caller/callee and pointer-ref provenance found no CAB, SerializedFile, global-metadata, AssetBundle, LuaScripts payload, keyword/import, or file-buffer owner path for these shape-only leads.
  - Next lead from the external analysis log: `0x4a471a`.
  - Use: negative routing evidence to avoid repeating broad shape-only NEP2 scans.

- `nslg-client-import-queue-round36.yaml`
  - Source: review/decoder queue built from the round35 evidence bundle plus decoded hero staging, LuaScripts TextAsset catalog, LuaScripts crypto evidence, and NEP2 static evidence.
  - Scope: 87 queue items: 63 decoded hero review candidates, 16 LuaScripts decoder targets, 4 Lua crypto decoder targets, and 4 NEP2 static trace targets.
  - Readiness: `safe_for_publish=false`, `auto_publish_allowed=false`; this is planning material, not a publish command.
  - Use: sorted next-work queue for manual review, decoder narrowing, evidence refs, blockers, and qa-agent import readiness tracking.

- `nslg-client-evidence-bundle-round35.yaml`
  - Source: aggregate bundle over the current offline client-package evidence artifacts.
  - Scope: 5 artifacts, 317 evidence refs, client app version `1.29.0`.
  - Readiness: `safe_for_publish=false`; 63 decoded hero staging entries remain normalized, and LuaScripts/NEP2 artifacts remain decoder targets.
  - Use: single qa-agent import-planning entry point for version tracking, evidence refs, review blockers, decoder targets, and next actions.

- `nslg-pc-1.29.0-manifest.yaml`
  - Source: PC client install scan.
  - Version anchors: app version `1.29.0`, package info `1.29.0.0`, app git `0de45a91`, bundle git `7a56faae`.
  - Scope: 187 included files, 491 skipped runtime/log/database files.
  - Use: version tracking, binary/asset anchor discovery, future extractor routing.

- `nslg-luascripts-textassets-round31-catalog.yaml`
  - Source: offline Unity TextAsset extraction summary from the `luascripts.ns` asset bundle.
  - Scope: 104 cataloged TextAsset records, 16 unique stems, 23 scenarios.
  - High-value stems: `heros`, `skills`, `warbook`, `army_config`, `battle_record`, `battle_replay`, `battle_reports`, `custom_hero`, `hero_story`, `hero_talent`, `scene_building_skill`, `sandbox_battle_config`, `water_battle`.
  - Current status: all cataloged payloads are `obfuscated_binary_pending_decoder`; the catalog is evidence metadata, not publishable game knowledge.

- `nslg-luascripts-crypto-evidence-round32.yaml`
  - Source: sanitized LuaScripts payload transform/decryptor evidence scan.
  - Scope: 3 binary string-hit summaries, 9 payload block samples, 1 Lua runtime initialize entry.
  - Current finding: sampled LuaScripts payloads are high-entropy, 16-byte aligned, and have no duplicate 16-byte blocks, consistent with AES or another 16-byte block transform.
  - Next decoder targets: `xluaL_loadbuffer` / `TextAsset::get_bytes`, `NSLGame.Patcher.GameUpdater.InitLuaEnv`, and protected `global-metadata.dat`.

- `nslg-nep2-luascripts-evidence-round34.yaml`
  - Source: sanitized NEP2 LuaScripts/protector static scan.
  - Scope: 3 `InitLuaScriptsScan` occurrences, 14 selected Lua/protection strings, 6 xrefs to `O3P1P1_1P2P3WAES`.
  - Current finding: NEP2 exposes concrete `CGameProtector::InitLuaScriptsScan` evidence and is the next static target for the LuaScripts decoder route.
  - The `O3P1P1_1P2P3WAES` xref windows register string chunks `O3`, `P1`, `P1_1`, `P2`, `P3`, and `WAES` through helper `0x180021240`; this looks like descriptor/string registration evidence, not the decryptor body by itself.
  - Next decoder targets: `CGameProtector::InitLuaScriptsScan`, `LuaJitLuaSrcLuaSrcEncrytedLuacCompiled`, `luaL_loadbuffer`, and the xref windows calling `0x180021240`.

Related staging artifacts live under `packages/qa-agent/ingestion/staging/client_decoded/`:

- `nslg-hero-readable-export-round29-normalized.yaml`
  - 63 normalized hero-profile candidates from decoded local hero export.
  - Publish is blocked until manual review.

- `nslg-hero-readable-export-round29-audit.yaml`
  - 62 mapped hero IDs, 1 unmapped hero ID, 57 mapped skill IDs, 17 unmapped skill IDs.
  - Sensitive staged-output scan found 0 runtime/account-local markers.
  - Main blockers: normalized-not-reviewed status, unmapped IDs, low-confidence mappings, missing formal skill profiles.

## Rebuild Commands

```bash
PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.scan_nslg_client \
  --root '<NSLG Game install root>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-pc-1.29.0-manifest.yaml

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_gameassembly_metadata_registration_candidate_taxonomy \
  --input '<threads/artifacts/gameassembly_metadata_registration_candidate_taxonomy_round185.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-metadata-registration-candidate-taxonomy-round118.yaml \
  --source-id gameassembly-metadata-registration-candidate-taxonomy-round118

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_gameassembly_global_metadata_owner_probe \
  --input '<threads/artifacts/gameassembly_global_metadata_owner_probe_round188.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-global-metadata-owner-probe-round127.yaml \
  --source-id gameassembly-global-metadata-owner-probe-round127

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.build_client_evidence_bundle \
  --repo-root packages/qa-agent \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-client-evidence-bundle-round128.yaml \
  --source-id nslg-client-offline-bundle-round128 \
  --gameassembly-global-metadata-owner-probe packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-global-metadata-owner-probe-round127.yaml \
  --gameassembly-metadata-registration-candidate-taxonomy packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-metadata-registration-candidate-taxonomy-round118.yaml

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.build_client_import_queue \
  --repo-root packages/qa-agent \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-client-import-queue-round129.yaml \
  --source-id nslg-client-import-queue-round129 \
  --evidence-bundle packages/qa-agent/ingestion/raw/client_packages/nslg-client-evidence-bundle-round128.yaml \
  --gameassembly-global-metadata-owner-probe packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-global-metadata-owner-probe-round127.yaml \
  --gameassembly-metadata-registration-candidate-taxonomy packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-metadata-registration-candidate-taxonomy-round118.yaml

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.build_client_evidence_bundle \
  --repo-root packages/qa-agent \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-client-evidence-bundle-round104.yaml \
  --source-id nslg-client-offline-bundle-round104

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.build_client_import_queue \
  --repo-root packages/qa-agent \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-client-import-queue-round105.yaml \
  --source-id nslg-client-import-queue-round105 \
  --evidence-bundle packages/qa-agent/ingestion/raw/client_packages/nslg-client-evidence-bundle-round104.yaml \
  --runtime-init-registry-probe packages/qa-agent/ingestion/raw/client_packages/nslg-runtime-init-registry-probe-round97.yaml \
  --gameassembly-codegen-module-probe packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-codegen-module-probe-round100.yaml \
  --gameassembly-registration-anchor-probe packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-registration-anchor-probe-round103.yaml

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_gameassembly_route_trace \
  --input-dir '<threads/artifacts>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-route-trace-round43.yaml \
  --source-id gameassembly-route-trace-round43

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_init_bridge \
  --input '<threads/artifacts/nep2_init_luascripts_bridge_summary_round161.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-init-bridge-round46.yaml \
  --source-id nep2-init-bridge-round46

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_luascripts_payload_cipher_profile \
  --input '<threads/artifacts/luascripts_payload_cipher_profile_round162.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-luascripts-payload-cipher-profile-round49.yaml \
  --source-id luascripts-payload-cipher-profile-round49

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_luascripts_payload_variant_corpus \
  --input '<threads/artifacts/luascripts_payload_variant_corpus_round172.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-luascripts-payload-variant-corpus-round79.yaml \
  --source-id nslg-luascripts-payload-variant-corpus-round79

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_textasset_payload_owner_trace \
  --input '<threads/artifacts/textasset_payload_owner_trace_round173.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-textasset-payload-owner-trace-round82.yaml \
  --source-id textasset-payload-owner-trace-round82

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_serialized_textasset_layout \
  --input '<threads/artifacts/serialized_textasset_layout_probe_round174.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-serialized-textasset-layout-round85.yaml \
  --source-id serialized-textasset-layout-round85

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_serialized_textasset_resolution \
  --input '<threads/artifacts/serialized_textasset_path_resolution_round175.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-serialized-textasset-path-resolution-round88.yaml \
  --source-id serialized-textasset-path-resolution-round88

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_resolved_payload_native_anchor_scan \
  --input '<threads/artifacts/resolved_payload_native_anchor_scan_round176.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-resolved-payload-native-anchor-scan-round91.yaml \
  --source-id resolved-payload-native-anchor-scan-round91

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_textasset_xlua_boundary_ledger \
  --input '<threads/artifacts/textasset_xlua_boundary_ledger_round177.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-textasset-xlua-boundary-ledger-round94.yaml \
  --source-id textasset-xlua-boundary-ledger-round94

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_runtime_init_registry_probe \
  --input '<threads/artifacts/runtime_init_registry_probe_round178.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-runtime-init-registry-probe-round97.yaml \
  --source-id runtime-init-registry-probe-round97

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_gameassembly_codegen_module_probe \
  --input '<threads/artifacts/gameassembly_codegen_module_probe_round179.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-codegen-module-probe-round100.yaml \
  --source-id gameassembly-codegen-module-probe-round100

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_gameassembly_registration_anchor_probe \
  --input '<threads/artifacts/gameassembly_registration_anchor_probe_round180.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-registration-anchor-probe-round103.yaml \
  --source-id gameassembly-registration-anchor-probe-round103

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_native_loadbuffer_boundary \
  --input '<threads/artifacts/native_loadbuffer_boundary_trace_round163.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-native-loadbuffer-boundary-round52.yaml \
  --source-id native-loadbuffer-boundary-round52

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_runtime_init_metadata_route \
  --input '<threads/artifacts/runtime_init_metadata_route_round164.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-runtime-init-metadata-route-round55.yaml \
  --source-id runtime-init-metadata-route-round55

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_global_metadata_transform_probe \
  --input '<threads/artifacts/global_metadata_transform_probe_round167.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-global-metadata-transform-probe-round64.yaml \
  --source-id global-metadata-transform-probe-round64

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_global_metadata_loader_scan \
  --input '<threads/artifacts/global_metadata_loader_mutation_scan_round168.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-global-metadata-loader-scan-round67.yaml \
  --source-id global-metadata-loader-mutation-scan-round67

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_metadata_loader_deep_slice \
  --input '<threads/artifacts/nep2_global_metadata_loader_deep_slice_round169.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-global-metadata-loader-deep-slice-round70.yaml \
  --source-id nep2-global-metadata-loader-deep-slice-round70

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_read_mapping_owner_scan \
  --input '<threads/artifacts/nep2_read_mapping_owner_scan_round170.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-read-mapping-owner-scan-round73.yaml \
  --source-id nslg-nep2-read-mapping-owner-scan-round73

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_init_data_owner_scan \
  --input '<threads/artifacts/nep2_init_data_owner_scan_round171.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-init-data-owner-scan-round76.yaml \
  --source-id nslg-nep2-init-data-owner-scan-round76

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_vector_candidate_provenance \
  --input '<threads/artifacts/nep2_vector_candidate_provenance_round186.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-vector-candidate-provenance-round121.yaml \
  --source-id nep2-vector-candidate-provenance-round121

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_vector_wrapper_owner_probe \
  --input '<threads/artifacts/nep2_vector_wrapper_owner_probe_round189.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-vector-wrapper-owner-probe-round130.yaml \
  --source-id nep2-vector-wrapper-owner-probe-round130

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_client_resource_surface_gap_scan \
  --input '<threads/artifacts/client_resource_surface_gap_scan_round190.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-client-resource-surface-gap-scan-round133.yaml \
  --source-id client-resource-surface-gap-scan-round133

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_file_helper_caller_provenance \
  --input '<threads/artifacts/nep2_file_helper_caller_provenance_round187.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-file-helper-caller-provenance-round124.yaml \
  --source-id nep2-file-helper-caller-provenance-round124

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_gameassembly_resolver_trace \
  --input '<threads/artifacts/gameassembly_resolver_candidate_trace_round165.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-resolver-trace-round58.yaml \
  --source-id gameassembly-resolver-trace-round58

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_gameassembly_resolver_caller_trace \
  --input '<threads/artifacts/gameassembly_resolver_caller_payload_trace_round166.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-gameassembly-resolver-caller-trace-round61.yaml \
  --source-id gameassembly-resolver-caller-trace-round61

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_provenance_closures \
  --input-dir '<threads/artifacts>' \
  --analysis-log '<threads/nslg_local_data_analysis.md>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-provenance-closures-round40.yaml \
  --source-id nep2-provenance-closures-round40

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.catalog_luascripts_textassets \
  --input '<luascripts_textasset_extract_round31.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-luascripts-textassets-round31-catalog.yaml \
  --source-id luascripts-textasset-round31

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_luascripts_crypto_evidence \
  --input '<luascripts_decryptor_evidence_round32.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-luascripts-crypto-evidence-round32.yaml \
  --source-id luascripts-crypto-round32

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.summarize_nep2_luascripts_evidence \
  --candidate-scan '<nep2_luascripts_candidate_round34.json>' \
  --init-scan '<nep2_init_luascripts_scan_round34.json>' \
  --output packages/qa-agent/ingestion/raw/client_packages/nslg-nep2-luascripts-evidence-round34.yaml \
  --source-id nep2-luascripts-round34

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.stage_client_decoded_heroes \
  --input '<hero_readable_export_round29.json>' \
  --output packages/qa-agent/ingestion/staging/client_decoded/nslg-hero-readable-export-round29-normalized.yaml \
  --source-id hero-readable-export-round29 \
  --mappings packages/qa-agent/configs/client_decoded_mappings.yaml

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.audit_client_decoded_heroes \
  --input '<hero_readable_export_round29.json>' \
  --output packages/qa-agent/ingestion/staging/client_decoded/nslg-hero-readable-export-round29-audit.yaml \
  --source-id hero-readable-export-round29 \
  --mappings packages/qa-agent/configs/client_decoded_mappings.yaml \
  --knowledge-dir packages/qa-agent/knowledge_sources
```

## Guardrails

- Do not store account credentials, tokens, local account identifiers, chat, mail, troop counts, or raw local runtime databases here.
- Keep client-decoded entries in staging until review promotes them to `reviewed`.
- Treat LuaScripts TextAsset records as decoder targets until their payloads are readable and semantically validated.
- Treat LuaScripts payload variant corpus reports as decoder/eval evidence only; repeated encrypted payloads and block statistics are not gameplay facts.
- Treat native boundary traces as decoder-routing evidence only; do not promote import/export strings as gameplay facts.
- Treat runtime-init metadata route summaries as decoder planning only until protected metadata is decoded or method ownership is proven.
- Treat runtime-init registry probes as planning evidence only; managed registry names and loadTypes do not prove native method ownership.
- Treat GameAssembly CodeGenModule probes as registration-side evidence only; method pointer tables do not name `InitLuaEnv` without decoded metadata or metadata-registration ownership.
- Treat global-metadata transform probes as negative route evidence only; do not promote simple transform failures as decoded metadata.
- Treat global-metadata loader-mutation scans as static trace seeds only until file-buffer ownership, metadata wrapper provenance, and a validated IL2CPP header/string recovery are proven.
- Treat NEP2 metadata-loader deep-slice closures as route-demotion evidence only; they close named helper functions, not the full NEP2 loader surface.
- Treat NEP2 InitLuaScriptsScan data-owner scans as routing evidence only until payload-buffer provenance is attached.
- Treat NEP2 vector/helper candidate provenance as routing evidence only; unlinked vector helpers do not prove a decoder.
- Treat NEP2 vector-wrapper owner probes as route-closure evidence only; wrapper call edges do not prove decoder ownership without payload-buffer provenance.
- Treat client resource-surface gap scans as sanitized inventory only; `.ns` bundle presence and magic samples do not prove decoded gameplay facts.
- Treat GameAssembly resolver traces as descriptor evidence only until method ownership or payload-buffer provenance is proven.
- Treat GameAssembly resolver caller traces as negative route evidence unless a direct caller gains TextAsset/file-buffer provenance.
- Treat TextAsset/xLua boundary ledgers as route closure/planning evidence only; do not promote closed negative routes or encrypted payload anchors as gameplay facts.
- Treat GameAssembly MetadataRegistration candidate taxonomy as route evidence only; exact refs to tiny-count candidate families and unowned high-count windows do not prove method ownership.
