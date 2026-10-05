"""Apply identical exact-source/report assertions to the final immutable SHA."""
from pathlib import Path

source = (Path(__file__).parent / 'source_report_checks_2cc.py').read_text()
source = source.replace('2cc7b2f8-20261006', 'fece4163-20261006')
source = source.replace('2cc7b2f885b3d33b46c719b89fb3c85d2ade2e96', 'fece4163d04af5057493549da2db74a8fa65ed06')
source = source.replace('73309b5d5bf61b0c02765eb833e1c308bd04eec0', '4c25f8fa14ea99d8aca09d49cf6c3c911c5c2f8e')
source = source.replace('/tmp/h09a-cr-2cc7b2f8-', '/tmp/h09a-cr-fece4163-')
exec(compile(source, 'source_report_checks_2cc_rebound_to_fece.py', 'exec'))
