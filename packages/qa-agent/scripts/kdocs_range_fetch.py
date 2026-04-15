"""Fetch specific files from a remote xlsx via HTTP Range — avoid downloading the full 60MB.

Given kdocs download URL, parse EOCD/central directory from a tail fetch, then range-
fetch the local file header + compressed data for each requested inner path and
decompress (DEFLATE, method=8). Use when full-file download is bandwidth-prohibitive
(e.g. kdocs hwc-bj CDN throttled from international IPs to <5 KB/s).

Usage:
  python3 kdocs_range_fetch.py --url-file /tmp/du.txt --size 60943718 \
    --out-dir /tmp/sheets --want xl/workbook.xml xl/sharedStrings.xml \
    xl/worksheets/sheet1.xml
"""
from __future__ import annotations

import argparse
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path


def curl_range(url: str, lo: int, hi: int, dest: Path, timeout: int = 120) -> int:
    """Return bytes written. Retries once on partial read."""
    for attempt in range(3):
        proc = subprocess.run(
            [
                "curl", "-sS", "--max-time", str(timeout),
                "-A", "Mozilla/5.0",
                "-H", f"Range: bytes={lo}-{hi}",
                "-o", str(dest),
                url,
            ],
            capture_output=True,
        )
        n = dest.stat().st_size if dest.exists() else 0
        expected = hi - lo + 1
        if n >= expected:
            return n
        print(f"  attempt {attempt+1}: got {n}/{expected}, retry...", file=sys.stderr)
        time.sleep(2)
    return dest.stat().st_size if dest.exists() else 0


def parse_eocd_and_cd(url: str, file_size: int) -> list[tuple[str, int, int, int, int]]:
    """Return [(name, local_offset, comp_size, uncomp_size, method), ...]."""
    tail_size = min(65536, file_size)
    tail_path = Path("/tmp/_xlsx_tail")
    print(f"Fetching tail {file_size - tail_size}..{file_size - 1}...")
    curl_range(url, file_size - tail_size, file_size - 1, tail_path)
    tail = tail_path.read_bytes()
    tail_start = file_size - len(tail)

    eocd = tail.rfind(b"\x50\x4b\x05\x06")
    if eocd < 0:
        raise SystemExit("EOCD not found")
    rec = tail[eocd : eocd + 22]
    (_sig, _d, _cd_d, _en_d, _en_t, cd_size, cd_off, _cmt) = struct.unpack(
        "<IHHHHIIH", rec
    )
    if cd_off == 0xFFFFFFFF:
        raise SystemExit("zip64 not supported")
    print(f"CD offset={cd_off} size={cd_size}")

    # CD may be outside current tail; fetch it explicitly
    if cd_off < tail_start:
        cd_path = Path("/tmp/_xlsx_cd")
        curl_range(url, cd_off, cd_off + cd_size - 1, cd_path)
        cd = cd_path.read_bytes()
    else:
        cd = tail[cd_off - tail_start : cd_off - tail_start + cd_size]

    entries = []
    i = 0
    while i < len(cd):
        (_sig, _vm, _vn, _fl, method, _mt, _md, _crc,
         comp_size, uncomp_size, name_len, extra_len, comment_len,
         _dn, _ia, _ea, local_offset) = struct.unpack("<IHHHHHHIIIHHHHHII", cd[i : i + 46])
        name = cd[i + 46 : i + 46 + name_len].decode("utf-8", errors="replace")
        entries.append((name, local_offset, comp_size, uncomp_size, method))
        i += 46 + name_len + extra_len + comment_len
    return entries


def fetch_and_extract(url: str, entry, out_path: Path) -> None:
    name, local_off, comp_size, uncomp_size, method = entry
    # Local header is 30 bytes + name + extra. Pull a generous buffer.
    pad = 512
    lo = local_off
    hi = local_off + 30 + pad + comp_size - 1
    raw_path = Path("/tmp/_xlsx_raw")
    print(f"  fetching {name} ({hi-lo+1} bytes)...")
    t0 = time.time()
    curl_range(url, lo, hi, raw_path)
    data = raw_path.read_bytes()
    if data[:4] != b"\x50\x4b\x03\x04":
        raise RuntimeError(f"bad local header for {name}")
    lh_name_len = struct.unpack("<H", data[26:28])[0]
    lh_extra_len = struct.unpack("<H", data[28:30])[0]
    lh_method = struct.unpack("<H", data[8:10])[0]
    data_start = 30 + lh_name_len + lh_extra_len
    blob = data[data_start : data_start + comp_size]
    if lh_method == 0:
        payload = blob
    elif lh_method == 8:
        payload = zlib.decompress(blob, -15)
    else:
        raise RuntimeError(f"unsupported method {lh_method}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)
    dt = time.time() - t0
    print(f"    wrote {out_path} ({len(payload)} bytes, {dt:.1f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-file", required=True)
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--want", nargs="+", required=True)
    args = ap.parse_args()

    url = Path(args.url_file).read_text().strip()
    entries = parse_eocd_and_cd(url, args.size)
    by_name = {n: (n, o, c, u, m) for n, o, c, u, m in entries}
    out_dir = Path(args.out_dir)
    for want in args.want:
        if want not in by_name:
            print(f"NOT FOUND: {want}")
            continue
        fetch_and_extract(url, by_name[want], out_dir / want)


if __name__ == "__main__":
    main()
