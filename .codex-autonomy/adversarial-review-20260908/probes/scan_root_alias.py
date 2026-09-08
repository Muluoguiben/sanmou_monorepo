import json,tempfile
from pathlib import Path
from qa_agent.ingestion.client_package import scan_client_package
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)/'game-install';root.mkdir();private=root/'LocalPersistentData';private.mkdir();(private/'account-cache.txt').write_text('SYNTHETIC_PRIVATE_ROOT_MARKER',encoding='ascii');alias=root/'public-root';alias.symlink_to(private,target_is_directory=True)
 try:
  out=scan_client_package(alias);leaked=any('SYNTHETIC_PRIVATE_ROOT_MARKER' in f.head_ascii for f in out.files);result={'root_symlink':True,'runtime_opt_in':out.scan_policy['include_runtime_files'],'included':out.included_files,'private_marker_emitted':leaked,'rejected':False}
 except (OSError,ValueError) as exc:result={'root_symlink':True,'rejected':True,'error_type':type(exc).__name__};leaked=False
 print(json.dumps(result));assert not leaked,'root normalization bypassed link/runtime exclusion policy'
