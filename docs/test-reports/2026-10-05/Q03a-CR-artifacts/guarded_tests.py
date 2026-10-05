"""Independent offline test launcher; no provider configuration or networking."""
import os
from pathlib import Path
import runpy
import socket
import sys

ROOT = Path(__file__).resolve().parents[4]
QA = ROOT / "packages/qa-agent"
sys.path[:0] = [str(QA), str(QA / "src"), str(QA / "tests"),
                str(ROOT / "packages/sanmou-common/src"),
                str(ROOT / "packages/pioneer-agent/src"),
                str(ROOT / "packages/pioneer-agent/tests/unit"),
                str(Path(__file__).parent)]

def forbidden(path):
    try:
        name = Path(path).name.lower()
    except TypeError:
        return False
    return name == ".env" or name.startswith(".env.")

def audit(event, args):
    if event == "open" and args and forbidden(args[0]):
        raise AssertionError("credential file read forbidden")

# Preserve builtin function identity: production checks os.open in supports_dir_fd.
sys.addaudithook(audit)
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex

def no_inet_connect(sock, address):
    if sock.family != socket.AF_UNIX:
        raise AssertionError("network connection forbidden")
    return _connect(sock, address)

def no_inet_connect_ex(sock, address):
    if sock.family != socket.AF_UNIX:
        raise AssertionError("network connection forbidden")
    return _connect_ex(sock, address)

def no_dns(*a, **kw):
    raise AssertionError("DNS/network lookup forbidden")

socket.socket.connect = no_inet_connect
socket.socket.connect_ex = no_inet_connect_ex
socket.getaddrinfo = no_dns
sys.argv = ["unittest", *sys.argv[1:]]
runpy.run_module("unittest", run_name="__main__")
