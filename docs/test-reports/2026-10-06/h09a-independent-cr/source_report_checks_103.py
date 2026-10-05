"""Same exact-source/report assertions, rebound to final CR05 source."""
from pathlib import Path
source = (Path(__file__).parent / 'source_report_checks_2cc.py').read_text()
source = source.replace('2cc7b2f8-20261006', '103d0d15-20261006')
source = source.replace('2cc7b2f885b3d33b46c719b89fb3c85d2ade2e96', '103d0d1594a11af905515182913731d2d8bb4ac9')
source = source.replace('73309b5d5bf61b0c02765eb833e1c308bd04eec0', 'e9b80b3a76b494b73e0266cb383793cacb3e246d')
source = source.replace('/tmp/h09a-cr-2cc7b2f8-', '/tmp/h09a-cr-103d0d15-')
exec(compile(source, 'source_report_checks_2cc_rebound_to_103.py', 'exec'))
