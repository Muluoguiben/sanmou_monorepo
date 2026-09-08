from pathlib import Path
import json,sys
from qa_agent.ingestion.client_package import scan_client_package
base=Path(sys.argv[1]);root=base/'game-install';alias=root/'public-root';parent=base/'alias-parent';private=root/'LocalPersistentData'
assert alias.lstat().st_file_attributes & 0x400
cases={}
for name,target in [('root-junction',alias),('parent-junction',parent/'assets')]:
 for opt in (False,True):
  try:scan_client_package(target,include_runtime_files=opt)
  except ValueError:cases[f'{name}/runtime={opt}']='rejected'
  else:raise AssertionError('junction accepted')
normal=scan_client_package(root);assert normal.included_files==1 and normal.files[0].head_ascii=='SYNTHETIC_PUBLIC'
try:scan_client_package(private)
except ValueError:cases['private-default']='rejected'
else:raise AssertionError('runtime root accepted without opt-in')
opted=scan_client_package(private,include_runtime_files=True);assert opted.included_files==1
print(json.dumps({'native_windows_junction_attribute':True,'cases':cases,'normal_public_files':normal.included_files,'explicit_real_runtime_root_files':opted.included_files,'real_account_data_read':False}))
