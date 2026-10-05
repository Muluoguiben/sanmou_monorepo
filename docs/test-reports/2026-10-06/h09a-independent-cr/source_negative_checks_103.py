"""Same real-CLI source negatives, explicitly rebound to CR05-fixed snapshots."""
from pathlib import Path
source = (Path(__file__).parent / 'source_negative_checks_2cc.py').read_text()
source = source.replace('/tmp/h09a-cr-2cc-', '/tmp/h09a-cr-103d-')
exec(compile(source, 'source_negative_checks_2cc_rebound_to_103.py', 'exec'))
