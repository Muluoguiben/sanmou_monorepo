"""Rebind the unchanged real-CLI provenance negative checks to final source."""
from pathlib import Path
source = (Path(__file__).parent / 'source_negative_checks_2cc.py').read_text()
source = source.replace('/tmp/h09a-cr-2cc-', '/tmp/h09a-cr-fece-')
exec(compile(source, 'source_negative_checks_2cc_rebound_to_fece.py', 'exec'))
