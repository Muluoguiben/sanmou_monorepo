"""Replay CR05 unchanged except immutable source/root binding."""
from pathlib import Path
source = (Path(__file__).parent / 'editable_metadata_fece.py').read_text()
source = source.replace('/tmp/h09a-cr-fece-editable-metadata', '/tmp/h09a-cr-103d-editable-metadata')
source = source.replace('fece4163d04af5057493549da2db74a8fa65ed06', '103d0d1594a11af905515182913731d2d8bb4ac9')
exec(compile(source, 'editable_metadata_fece_rebound_to_103.py', 'exec'))
