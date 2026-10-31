#!/usr/bin/env python3
"""Runs the reader over a fixture directory from make_fixtures.py.

    interop_read.py QRTOOL DIR [--allow-failures CATEGORY=N ...]

Prints a table by category and, for scale, how zbar and ZXing do on the same
images. Exits non-zero when abla-qr misses a fixture or, worse, returns wrong data.
"""
import pathlib
import subprocess
import sys

import zxingcpp
from PIL import Image


def main():
    qrtool, folder = sys.argv[1], pathlib.Path(sys.argv[2])
    allowed = {}
    for argument in sys.argv[3:]:
        if "=" in argument:
            name, count = argument.split("=")
            allowed[name] = int(count)
    totals = {}
    wrong = 0
    for line in (folder / "manifest.tsv").read_text().splitlines():
        name, category, expected = line.split("\t")
        expected = bytes.fromhex(expected)
        path = folder / name
        row = totals.setdefault(category, [0, 0, 0, 0, []])
        row[0] += 1
        result = subprocess.run([qrtool, "decode", str(path)], capture_output=True, timeout=120)
        if result.returncode == 0 and result.stdout == expected:
            row[1] += 1
        else:
            row[4].append(name)
            if result.returncode == 0:
                wrong += 1
                print(f"WRONG DATA {name}")
            elif result.returncode not in (0, 1):
                print(f"CRASH {name}: {result.returncode} {result.stderr[:200]}")
        zbar = subprocess.run(["zbarimg", "-q", "--raw", "-Sbinary", "--oneshot", str(path)], capture_output=True)
        if zbar.returncode == 0 and zbar.stdout.rstrip(b"\n") == expected.rstrip(b"\n"):
            row[2] += 1
        found = zxingcpp.read_barcodes(Image.open(path).convert("L"))
        if found and found[0].bytes == expected:
            row[3] += 1
    print(f"{'category':16} {'total':>5} {'abla-qr':>8} {'zbar':>5} {'zxing':>6}")
    failed = wrong > 0
    for category, (total, ours, zbar, zxing, missed) in sorted(totals.items()):
        print(f"{category:16} {total:5} {ours:8} {zbar:5} {zxing:6}  {' '.join(missed)}")
        if total - ours > allowed.get(category, 0):
            failed = True
    sums = [sum(row[i] for row in totals.values()) for i in range(4)]
    print(f"{'all':16} {sums[0]:5} {sums[1]:8} {sums[2]:5} {sums[3]:6}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
