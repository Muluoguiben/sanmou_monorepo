"""Explicit source-root offline launcher; preserves native dir_fd identities."""
from pathlib import Path
import runpy
import socket
import sys

root = Path(sys.argv.pop(1)).resolve()
qa = root / "packages/qa-agent"
sys.path[:0] = [str(qa), str(qa / "src"), str(qa / "tests"),
    str(root / "packages/sanmou-common/src"), str(root / "packages/pioneer-agent/src"),
    str(root / "packages/pioneer-agent/tests/unit"),
    str(root / "docs/test-reports/2026-10-05/Q03a-repair-artifacts"),
    str(Path(__file__).resolve().parent)]

def audit(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        name = Path(args[0].decode() if isinstance(args[0], bytes) else args[0]).name.lower()
        if name == ".env" or name.startswith(".env."):
            raise AssertionError("credential/config file read forbidden")

sys.addaudithook(audit)
old_connect = socket.socket.connect
old_connect_ex = socket.socket.connect_ex

def connect(sock, address):
    if sock.family != socket.AF_UNIX:
        raise AssertionError("network forbidden")
    return old_connect(sock, address)

def connect_ex(sock, address):
    if sock.family != socket.AF_UNIX:
        raise AssertionError("network forbidden")
    return old_connect_ex(sock, address)

def no_dns(*args, **kwargs):
    raise AssertionError("DNS forbidden")

socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = no_dns
sys.argv = ["unittest", *sys.argv[1:]]
runpy.run_module("unittest", run_name="__main__")
