#!/usr/bin/env python3
"""Synthesizes reader fixtures: codes from other encoders put through transforms.

These images imitate what a camera does (rotation, perspective, blur, sensor
noise, uneven light, JPEG artifacts, curved paper, damage). They are synthesized
by this script, not photographs. Output is deterministic for a given seed:

    make_fixtures.py OUTPUT_DIR [--small]

writes PNG files and a manifest.tsv of `file<TAB>category<TAB>hex of the data`.
--small limits it to the set committed in tests/fixtures.
"""
import io
import math
import pathlib
import random
import subprocess
import sys
import tempfile

import numpy as np
import qrcode
import segno
import zxingcpp
from PIL import Image, ImageDraw, ImageFilter

TEXTS = [
    "https://example.com/menu?table=12",
    "WIFI:T:WPA;S:cafe;P:correct horse battery;;",
    "Olá, código de barras! Preço: 12,50 €",
    "HTTPS://EXAMPLE.ORG/A/B/C",
    "A:123456789*B:999999990*C:PT*D:FT*E:N*F:20261031*G:FT 2026/1*H:ABCD-1*I1:PT*I7:100.00*I8:23.00*N:23.00*O:123.00*Q:wJal*R:9999",
    "1234567890123456789012345",
    "BEGIN:VCARD\nVERSION:3.0\nFN:Ada Lovelace\nTEL:+351210000000\nEMAIL:ada@example.com\nEND:VCARD\n",
    "x" * 300,
    "Long text. " * 90,
]


def python_qrcode(data, level="M", version=None, box=6, border=4):
    levels = {"L": qrcode.ERROR_CORRECT_L, "M": qrcode.ERROR_CORRECT_M,
              "Q": qrcode.ERROR_CORRECT_Q, "H": qrcode.ERROR_CORRECT_H}
    qr = qrcode.QRCode(version=version, error_correction=levels[level], box_size=box, border=border)
    qr.add_data(data.encode())
    qr.make(fit=version is None)
    return qr.make_image().convert("L")


def segno_code(data, level="M", box=6, border=4):
    out = io.BytesIO()
    segno.make(data, error=level, micro=False, boost_error=False).save(out, kind="png", scale=box, border=border)
    out.seek(0)
    return Image.open(out).convert("L")


def qrencode_code(data, level="M", box=6, border=4):
    with tempfile.NamedTemporaryFile(suffix=".png") as handle:
        subprocess.run(["qrencode", "-l", level, "-s", str(box), "-m", str(border), "-o", handle.name, "--", data],
                       check=True)
        return Image.open(handle.name).convert("L").copy()


def paste_on_background(rng, code, size, gray=235):
    """The code on textured paper, with room for transforms."""
    noise = np.random.default_rng(rng.randrange(1 << 30)).normal(gray, 6, (size, size))
    back = Image.fromarray(np.clip(noise, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    back.paste(code, ((size - code.width) // 2, (size - code.height) // 2))
    return back


def perspective_coefficients(source, target):
    rows = []
    for (x, y), (u, v) in zip(target, source):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return np.linalg.solve(np.array(rows, float), np.array(source, float).reshape(8))


def perspective(image, shift, rng, fill=235):
    w, h = image.size
    source = [(0, 0), (w, 0), (w, h), (0, h)]
    target = [(x + rng.uniform(-shift, shift) * w, y + rng.uniform(-shift, shift) * h) for x, y in source]
    return image.transform(image.size, Image.PERSPECTIVE, perspective_coefficients(source, target),
                            Image.BICUBIC, fillcolor=fill)


def shear(image, x_factor, y_factor, fill=235):
    w, h = image.size
    a = (1, x_factor, -x_factor * h / 2, y_factor, 1, -y_factor * w / 2)
    return image.transform(image.size, Image.AFFINE, a, Image.BICUBIC, fillcolor=fill)


def cylinder(image, strength, fill=235):
    """As if printed on a can: columns squeezed towards the edges, rows bowed."""
    a = np.asarray(image, float)
    h, w = a.shape
    ys, xs = np.mgrid[0:h, 0:w]
    nx = (xs - w / 2) / (w / 2)
    source_x = w / 2 + (w / 2) * np.sin(nx * strength) / math.sin(strength)
    source_y = ys + (h * 0.06 * strength) * (nx ** 2) * ((ys - h / 2) / (h / 2))
    x0 = np.clip(np.floor(source_x).astype(int), 0, w - 2)
    y0 = np.clip(np.floor(source_y).astype(int), 0, h - 2)
    fx = np.clip(source_x - x0, 0, 1)
    fy = np.clip(source_y - y0, 0, 1)
    out = (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy) +
           a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)
    return Image.fromarray(out.astype(np.uint8))


def uneven_light(image, rng, depth=0.6):
    """Dark corner to bright corner, with a soft shadow falling across."""
    a = np.asarray(image, float)
    h, w = a.shape
    ys, xs = np.mgrid[0:h, 0:w]
    angle = rng.uniform(0, 2 * math.pi)
    ramp = (xs * math.cos(angle) + ys * math.sin(angle))
    ramp = (ramp - ramp.min()) / (ramp.max() - ramp.min())
    return Image.fromarray(np.clip(a * (1 - depth + depth * ramp), 0, 255).astype(np.uint8))


def sensor_noise(image, rng, sigma):
    a = np.asarray(image, float)
    noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, sigma, a.shape)
    return Image.fromarray(np.clip(a + noise, 0, 255).astype(np.uint8))


def jpeg(image, quality):
    out = io.BytesIO()
    image.convert("RGB").save(out, "JPEG", quality=quality)
    out.seek(0)
    return Image.open(out).convert("L")


def camera(image, rng, blur=1.0, noise=5, quality=70):
    """The last stages every simulated shot goes through."""
    return jpeg(sensor_noise(image.filter(ImageFilter.GaussianBlur(blur)), rng, noise), quality)


def module_box(code_image, border=4, box=6):
    """Inner code area of a generated image."""
    return border * box, code_image.width - border * box


def blotches(code, rng, count, radius, color=None):
    out = code.copy()
    draw = ImageDraw.Draw(out)
    low, high = module_box(code)
    placed = 0
    while placed < count:
        x, y = rng.uniform(low, high), rng.uniform(low, high)
        # Keep off the finder patterns: without all three the code can't be located.
        finder = 9 * 6 + low
        if (x < finder and y < finder) or (x > high - 9 * 6 and y < finder) or (x < finder and y > high - 9 * 6):
            continue
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=color if color is not None else rng.choice((0, 255)))
        placed += 1
    return out


def centre_logo(code, fraction):
    out = code.copy()
    draw = ImageDraw.Draw(out)
    side = code.width * fraction
    middle = code.width / 2
    draw.rounded_rectangle((middle - side / 2, middle - side / 2, middle + side / 2, middle + side / 2), 8, fill=255,
                           outline=0, width=4)
    return out


def scratches(code, rng, count):
    out = code.copy()
    draw = ImageDraw.Draw(out)
    low, high = module_box(code)
    for _ in range(count):
        draw.line((rng.uniform(low, high), rng.uniform(low, high), rng.uniform(low, high), rng.uniform(low, high)),
                  fill=rng.choice((0, 255)), width=3)
    return out


def small_set(rng):
    yield "rotated-30", "rotated", TEXTS[0], python_qrcode(TEXTS[0]).rotate(30, Image.BICUBIC, expand=True, fillcolor=255)
    yield "rotated-135-noise", "rotated", TEXTS[1], camera(paste_on_background(rng, python_qrcode(TEXTS[1]), 520).rotate(135, Image.BICUBIC, fillcolor=235), rng)
    yield "perspective-strong", "perspective", TEXTS[2], camera(perspective(paste_on_background(rng, python_qrcode(TEXTS[2], "Q"), 620), 0.13, rng), rng)
    yield "sheared", "skewed", TEXTS[3], camera(shear(paste_on_background(rng, segno_code(TEXTS[3]), 560), 0.32, 0.12), rng)
    yield "uneven-light", "lighting", TEXTS[4], camera(uneven_light(paste_on_background(rng, python_qrcode(TEXTS[4]), 700), rng, 0.8), rng)
    yield "damaged-blotches", "damaged", TEXTS[0], camera(blotches(python_qrcode(TEXTS[0], "H"), rng, 5, 11), rng)
    yield "damaged-logo", "damaged", TEXTS[0], centre_logo(qrencode_code(TEXTS[0], "H", 8), 0.2)
    yield "curved-can", "curved", TEXTS[6], cylinder(paste_on_background(rng, python_qrcode(TEXTS[6], "M", box=7), 760), 0.75)
    yield "large-version", "perspective", TEXTS[8], camera(perspective(paste_on_background(rng, python_qrcode(TEXTS[8], "L", box=4), 1000), 0.04, rng), rng, 0.6, 3, 85)
    yield "inverted", "inverted", TEXTS[0], Image.eval(python_qrcode(TEXTS[0]), lambda p: 255 - p)
    yield "mirrored", "mirrored", TEXTS[0], python_qrcode(TEXTS[0]).transpose(Image.FLIP_LEFT_RIGHT)
    yield "tiny-rotated", "small", TEXTS[0], jpeg(python_qrcode(TEXTS[0], box=3).rotate(17, Image.BICUBIC, expand=True, fillcolor=255), 80)


def stress_set(rng):
    """Beyond what a reader is promised; failures here are measured, not errors."""
    for index, shift in enumerate([0.14, 0.17, 0.2, 0.23] * 3):
        text = TEXTS[index % 7]
        code = paste_on_background(rng, python_qrcode(text, "M"), 900)
        yield f"stress-perspective-{index}", "stress-perspective", text, camera(perspective(code, shift, rng), rng)
    for index, angle in enumerate([11, 37, 62, 148, 201, 299]):
        text = TEXTS[index % 7]
        code = paste_on_background(rng, python_qrcode(text, "M", box=2, border=4), 500)
        yield f"stress-small-{index}", "stress-small", text, camera(code.rotate(angle, Image.BICUBIC, fillcolor=235), rng, 0.6, 4, 75)
    for index, strength in enumerate([1.1, 1.25, 1.4]):
        text = TEXTS[index + 4]
        code = paste_on_background(rng, python_qrcode(text, "M", box=8), 900)
        yield f"stress-curved-{index}", "stress-curved", text, camera(cylinder(code, strength), rng, 0.8, 4, 75)
    for index, sigma in enumerate([3.5, 4.5, 5.5]):
        yield f"stress-blur-{index}", "stress-blur", TEXTS[0], python_qrcode(TEXTS[0], "M", box=8).filter(ImageFilter.GaussianBlur(sigma))
    for index, count in enumerate([8, 10, 12, 14]):
        yield f"stress-scratch-{index}", "stress-damage", TEXTS[1], camera(scratches(python_qrcode(TEXTS[1], "Q"), rng, count), rng)


def modes_set():
    """Modes abla-qr doesn't create but must read."""
    with tempfile.NamedTemporaryFile(suffix=".png") as handle:
        # qrencode -k takes Shift JIS, and from standard input as raw bytes.
        kanji = "\u70b9\u8317\u6f22\u5b57".encode("shift_jis")
        subprocess.run(["qrencode", "-k", "-s", "6", "-o", handle.name], input=kanji, check=True)
        yield "kanji-qrencode", "modes", kanji, Image.open(handle.name).convert("L").copy()
    out = io.BytesIO()
    segno.make("Ol\u00e1 mundo", eci=True, encoding="utf-8", mode="byte", micro=False).save(out, kind="png", scale=6)
    out.seek(0)
    yield "eci-utf8-segno", "modes", "Ol\u00e1 mundo", Image.open(out).convert("L").copy()
    for index, symbol in enumerate(segno.make_sequence("Structured append splits data over symbols.", symbol_count=2)):
        out = io.BytesIO()
        symbol.save(out, kind="png", scale=6)
        out.seek(0)
        image = Image.open(out).convert("L").copy()
        # What this symbol alone holds is the encoder's choice; ZXing says.
        yield f"structured-append-{index}", "modes", zxingcpp.read_barcodes(image)[0].bytes, image
    for digits in ("0", "12", "123", "1234567"):
        yield f"numeric-{digits}", "modes", digits, qrencode_code(digits, "H")


def full_set(rng):
    yield from modes_set()
    yield from stress_set(rng)
    yield from small_set(rng)
    makers = [("pyqrcode", python_qrcode), ("segno", segno_code), ("qrencode", qrencode_code)]
    for index, text in enumerate(TEXTS):
        level = "LMQH"[index % 4]
        if len(text.encode()) > 700 and level in "QH":
            level = "M"
        for name, maker in makers:
            yield f"clean-{name}-{index}", "other-encoder", text, maker(text, level)
    for angle in range(0, 360, 15):
        text = TEXTS[angle // 15 % 7]
        code = paste_on_background(rng, python_qrcode(text, "Q" if angle % 2 else "M"), 900)
        yield f"rotate-{angle}", "rotated", text, camera(code.rotate(angle, Image.BICUBIC, fillcolor=235), rng)
    for index in range(16):
        text = TEXTS[index % 7]
        code = paste_on_background(rng, python_qrcode(text, "M"), 900)
        yield f"perspective-{index}", "perspective", text, camera(perspective(code, 0.05 + 0.1 * (index % 4) / 3, rng), rng)
    for index, (x, y) in enumerate([(0.2, 0), (0, 0.2), (0.35, 0), (0, 0.35), (0.3, 0.2), (-0.3, 0.15), (0.25, -0.25), (-0.4, 0)]):
        text = TEXTS[index % 7]
        yield f"skew-{index}", "skewed", text, camera(shear(paste_on_background(rng, segno_code(text), 900), x, y), rng)
    for index in range(10):
        text = TEXTS[index % 7]
        code = paste_on_background(rng, python_qrcode(text, "M"), 800)
        yield f"light-{index}", "lighting", text, camera(uneven_light(code, rng, 0.5 + 0.04 * index), rng)
    for index, sigma in enumerate([1.0, 1.5, 2.0, 2.5, 3.0]):
        text = TEXTS[index % 5]
        code = python_qrcode(text, "M", box=8)
        yield f"blur-{index}", "blur", text, jpeg(code.filter(ImageFilter.GaussianBlur(sigma)), 80)
    for index, sigma in enumerate([10, 20, 30, 40]):
        yield f"noise-{index}", "noise", TEXTS[0], sensor_noise(python_qrcode(TEXTS[0], "M", box=8), rng, sigma)
    for index in range(16):
        text = TEXTS[0]
        code = blotches(python_qrcode(text, "H"), rng, 3 + index // 2, 8 + index % 4)
        yield f"blotch-{index}", "damaged", text, camera(code, rng)
    for index in range(8):
        text = TEXTS[1]
        yield f"scratch-{index}", "damaged", text, camera(scratches(python_qrcode(text, "Q"), rng, 2 + index), rng)
    for index, fraction in enumerate([0.15, 0.2, 0.25]):
        yield f"logo-{index}", "damaged", TEXTS[0], centre_logo(python_qrcode(TEXTS[0], "H", box=8), fraction)
    for index, strength in enumerate([0.4, 0.6, 0.8, 1.0]):
        text = TEXTS[6 - index]
        code = paste_on_background(rng, python_qrcode(text, "M", box=8), 900)
        yield f"cylinder-{index}", "curved", text, cylinder(code, strength)
    for box in (2, 3, 4):
        yield f"tiny-{box}", "small", TEXTS[0], python_qrcode(TEXTS[0], box=box)
        yield f"tiny-rot-{box}", "small", TEXTS[0], python_qrcode(TEXTS[0], box=box).rotate(23, Image.BICUBIC, expand=True, fillcolor=255)
    yield "contrast-low", "lighting", TEXTS[0], Image.eval(python_qrcode(TEXTS[0]), lambda p: 110 + p // 8)
    for version in (5, 10, 15, 20, 25, 30, 35, 40):
        text = "".join(random.Random(version).choice("abcdefghij 0123456789") for _ in range(version * version // 2 + 20))
        code = python_qrcode(text, "L", version=version, box=4)
        yield f"high-version-{version}", "large", text, camera(perspective(paste_on_background(rng, code, code.width + 120), 0.015, rng), rng, 0.5, 2, 90)


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261031)
    sets = small_set(rng) if "--small" in sys.argv else full_set(rng)
    lines = []
    for name, category, text, image in sets:
        image.save(out / f"{name}.png", optimize=True)
        data = text if isinstance(text, bytes) else text.encode()
        lines.append(f"{name}.png\t{category}\t{data.hex()}")
    (out / "manifest.tsv").write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} fixtures in {out}")


if __name__ == "__main__":
    main()
