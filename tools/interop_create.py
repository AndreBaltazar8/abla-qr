#!/usr/bin/env python3
"""Checks codes abla-qr creates against independent implementations.

- Module matrices must equal another encoder's, bit for bit, for every version
  and level and, on a sample of versions, every mask: segno for alphanumeric
  data and python-qrcode for byte data.
- zbar and ZXing must read the PNG output, and zbar the SVG output, for every
  version and level.
"""
import pathlib
import random
import subprocess
import sys
import tempfile

import qrcode
import segno
import zxingcpp
from PIL import Image

QRTOOL = sys.argv[1]
LEVELS = "LMQH"
# Data codewords per version and level aren't needed here: payloads are sized
# from what segno itself says fits, so a table error shows up as a mismatch.
ALPHANUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 $%*+-./:"
failures = []


def fail(message):
    failures.append(message)
    print("FAIL", message)


def run_tool(*args):
    subprocess.run([QRTOOL, *args], check=True)


def capacity(version, level, mode):
    """Longest payload for the mode, found by asking segno."""
    low, high = 1, 8000
    while low < high:
        middle = (low + high + 1) // 2
        data = "A" * middle if mode == "alphanumeric" else ("é" * (middle // 2)) + "x" * (middle % 2)
        try:
            segno.make(data, version=version, error=level, mode=mode, micro=False,
                       encoding="utf-8" if mode == "byte" else None, boost_error=False)
            low = middle
        except Exception:
            high = middle - 1
    return low


def payload(rng, length, mode):
    if mode == "alphanumeric":
        return "".join(rng.choice(ALPHANUM) for _ in range(length))
    text = ""
    while len(text.encode()) < length:
        text += rng.choice("abc xyzéã€\U0001f600 0123")
    while len(text.encode()) > length:
        text = text[:-1]
    # The automatic mode choice must land on byte mode for this test.
    return text if not text.isascii() else "é" + text[:-2]


def reference_rows(data, version, level, mask, mode):
    if mode == "alphanumeric":
        qr = segno.make(data, version=version, error=level, mask=mask, mode=mode, micro=False,
                        boost_error=False)
        return ["".join("1" if cell & 1 else "0" for cell in row) for row in qr.matrix]
    levels = {"L": qrcode.ERROR_CORRECT_L, "M": qrcode.ERROR_CORRECT_M,
              "Q": qrcode.ERROR_CORRECT_Q, "H": qrcode.ERROR_CORRECT_H}
    qr = qrcode.QRCode(version=version, error_correction=levels[level], mask_pattern=mask, border=0)
    qr.add_data(data.encode(), optimize=0)
    qr.make(fit=False)
    return ["".join("1" if cell else "0" for cell in row) for row in qr.get_matrix()]


def compare(tmp, data, version, level, mask, mode):
    out = tmp / "m.txt"
    source = tmp / "data.bin"
    source.write_bytes(data.encode())
    run_tool("encode", "--ec", level, "--version", str(version), "--mask", str(mask),
             "--format", "matrix", "--out", str(out), "--file", str(source))
    ours = out.read_text().split()
    theirs = reference_rows(data, version, level, mask, mode)
    if ours != theirs:
        fail(f"matrix v{version}-{level} mask {mask} {mode}")
        return False
    return True


def main():
    rng = random.Random(20261031)
    matrices = zbar_ok = zxing_ok = svg_ok = 0
    with tempfile.TemporaryDirectory() as temp:
        tmp = pathlib.Path(temp)
        for version in range(1, 41):
            for level in LEVELS:
                mode = "alphanumeric" if version % 2 else "byte"
                # Full capacity on most, to exercise padding-free and long blocks.
                length = capacity(version, level, mode)
                data = payload(rng, length, mode)
                masks = range(8) if version in (1, 2, 6, 7, 14, 21, 27, 32, 40) else [version % 8]
                for mask in masks:
                    if compare(tmp, data, version, level, mask, mode):
                        matrices += 1

                # Automatic mask, independent readers.
                source = tmp / "data.bin"
                source.write_bytes(data.encode())
                png = tmp / "code.png"
                svg = tmp / "code.svg"
                base = ("encode", "--ec", level, "--version", str(version), "--file", str(source))
                run_tool(*base, "--format", "png", "--scale", "4", "--out", str(png))
                run_tool(*base, "--format", "svg", "--scale", "4", "--out", str(svg))

                read = subprocess.run(["zbarimg", "-q", "--raw", "-Sbinary", "--oneshot", str(png)],
                                      capture_output=True)
                if read.stdout.rstrip(b"\n") == data.encode().rstrip(b"\n"):
                    zbar_ok += 1
                else:
                    fail(f"zbar png v{version}-{level}")

                found = zxingcpp.read_barcodes(Image.open(png).convert("L"))
                if found and found[0].bytes == data.encode():
                    zxing_ok += 1
                else:
                    fail(f"zxing png v{version}-{level}")

                rendered = tmp / "svg.png"
                subprocess.run(["rsvg-convert", "-o", str(rendered), str(svg)], check=True)
                read = subprocess.run(["zbarimg", "-q", "--raw", "-Sbinary", "--oneshot", str(rendered)],
                                      capture_output=True)
                if read.stdout.rstrip(b"\n") == data.encode().rstrip(b"\n"):
                    svg_ok += 1
                else:
                    fail(f"zbar svg v{version}-{level}")
    print(f"reference matrices equal: {matrices}")
    print(f"zbar read png: {zbar_ok}/160, zxing read png: {zxing_ok}/160, zbar read svg: {svg_ok}/160")
    print(f"{len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
