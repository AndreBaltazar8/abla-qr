#!/usr/bin/env python3
"""Writes tests/fixtures/png: every PNG colour type, depth, filter and Adam7.

Hand-rolled with zlib rather than through an image library, so the decoder is
tested on filters and layouts a library wouldn't choose. Each file is an 11x7
image of known samples; expected.txt lists the expected gray values of each.
"""
import pathlib
import struct
import sys
import zlib

WIDTH, HEIGHT = 11, 7
ADAM7 = [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
PALETTE = [(i * 16, 255 - i * 16, (i * 37) % 256) for i in range(16)]


def luma(r, g, b, a=255):
    value = (r * 77 + g * 150 + b * 29) >> 8
    return value if a >= 255 else (value * a + 255 * (255 - a)) // 255


def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def sample(x, y, depth):
    return (x * 13 + y * 29) * ((1 << depth) - 1) // (10 * 13 + 6 * 29)


def pixel(x, y, color, depth):
    """Channel samples and expected gray of one pixel."""
    s = sample(x, y, depth)
    full = lambda v: v * 255 // ((1 << depth) - 1) if depth < 8 else v >> (depth - 8)
    if color == 0:
        return [s], full(s)
    if color == 3:
        index = (x + y * 3) % (1 << min(depth, 4))
        return [index], luma(*PALETTE[index])
    t = sample(10 - x, y, depth)
    u = sample(x, 6 - y, depth)
    if color == 2:
        return [s, t, u], luma(full(s), full(t), full(u))
    a = sample(x, y, depth) // 2 + (1 << depth) // 2
    if color == 4:
        return [s, a], luma(full(s), full(s), full(s), full(a))
    return [s, t, u, a], luma(full(s), full(t), full(u), full(a))


def pack(samples, depth):
    if depth >= 8:
        return b"".join(v.to_bytes(depth // 8, "big") for v in samples)
    out, current, used = bytearray(), 0, 0
    for value in samples:
        current = (current << depth) | value
        used += depth
        if used == 8:
            out.append(current)
            current, used = 0, 0
    if used:
        out.append(current << (8 - used))
    return bytes(out)


def filter_row(row, previous, unit, kind):
    out = bytearray([kind])
    for i, value in enumerate(row):
        left = row[i - unit] if i >= unit else 0
        up = previous[i] if previous else 0
        corner = previous[i - unit] if previous and i >= unit else 0
        if kind == 0:
            predicted = 0
        elif kind == 1:
            predicted = left
        elif kind == 2:
            predicted = up
        elif kind == 3:
            predicted = (left + up) // 2
        else:
            p = left + up - corner
            pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
            predicted = left if pa <= pb and pa <= pc else (up if pb <= pc else corner)
        out.append((value - predicted) & 255)
    return bytes(out)


def build(color, depth, interlaced, level):
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    unit = max(1, channels * depth // 8)
    raw = bytearray()
    passes = ADAM7 if interlaced else [(0, 0, 1, 1)]
    for x0, y0, dx, dy in passes:
        previous = None
        row_number = 0
        for y in range(y0, HEIGHT, dy):
            samples = []
            for x in range(x0, WIDTH, dx):
                samples += pixel(x, y, color, depth)[0]
            if not samples:
                continue
            row = pack(samples, depth)
            raw += filter_row(row, previous, unit, row_number % 5)
            previous = row
            row_number += 1
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, depth, color, 0, 0, 1 if interlaced else 0))
    if color == 3:
        png += chunk(b"PLTE", b"".join(bytes(entry) for entry in PALETTE[:1 << min(depth, 4)]))
    compressed = zlib.compress(bytes(raw), level)
    # Two IDAT chunks, since a decoder must join them.
    png += chunk(b"IDAT", compressed[:5]) + chunk(b"IDAT", compressed[5:]) + chunk(b"IEND", b"")
    return png


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    combos = [(0, d) for d in (1, 2, 4, 8, 16)] + [(3, d) for d in (1, 2, 4, 8)] + \
        [(2, 8), (2, 16), (4, 8), (4, 16), (6, 8), (6, 16)]
    lines = []
    for color, depth in combos:
        expected = " ".join(str(pixel(x, y, color, depth)[1]) for y in range(HEIGHT) for x in range(WIDTH))
        for interlaced in (False, True):
            # Level 0 gives stored blocks, 1 fixed Huffman on this little data, 9 the rest.
            level = {1: 0, 2: 1}.get(depth, 9)
            name = f"c{color}d{depth}{'i' if interlaced else ''}.png"
            (out / name).write_bytes(build(color, depth, interlaced, level))
            lines.append(f"{name}|{expected}")
    (out / "expected.txt").write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} PNG fixtures")


if __name__ == "__main__":
    main()
