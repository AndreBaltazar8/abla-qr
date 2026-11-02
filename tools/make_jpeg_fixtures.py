#!/usr/bin/env python3
"""Writes tests/fixtures/jpeg: JPEG files of a code abla-qr's encoder made.

    make_jpeg_fixtures.py QRTOOL OUTPUT_DIR

Each file is the same code in colour, odd-sized so blocks and MCUs are cut at
the edges, written by Pillow or libjpeg-turbo's cjpeg in one layout: sampling,
progressive, restart markers, quality, EXIF, colour space. Beside each decodable
file is the gray image a reference decoder makes of it (`*.ref.png`, shared by
files that give the same image): djpeg's
`-grayscale` for gray and YCbCr, which is the Y component, and for RGB and CMYK
the luma of libjpeg's pixels with the weights of abla-qr's `qrLuma`.
`expected.tsv` lists `file<TAB>reference<TAB>tolerance<TAB>expected`, where
expected is the code's data in hex, or the error decoding must fail with.
"""
import io
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image

DATA = "A:123456789*B:999999990*C:PT*D:FT*Q:wJal"
DARK = (40, 30, 120)
LIGHT = (250, 240, 200)
WIDTH, HEIGHT = 83, 77


def luma(r, g, b):
    return (r * 77 + g * 150 + b * 29) >> 8


def run(*args, data=None):
    return subprocess.run(args, input=data, capture_output=True, check=True).stdout


def code_image(qrtool, folder):
    png = folder / "code.png"
    run(qrtool, "encode", "--ec", "M", "--scale", "2", "--border", "3", "--format", "png", "--out", str(png), "--text", DATA)
    code = Image.open(png).convert("L")
    image = Image.new("RGB", (WIDTH, HEIGHT), LIGHT)
    tinted = Image.new("RGB", code.size, LIGHT)
    tinted.paste(Image.new("RGB", code.size, DARK), mask=code.point(lambda v: 255 - v))
    image.paste(tinted, ((WIDTH - code.width) // 2 + 1, (HEIGHT - code.height) // 2))
    return image


def ppm(image):
    out = io.BytesIO()
    image.save(out, "PPM")
    return out.getvalue()


def cjpeg(image, *flags):
    return run("cjpeg", *flags, data=ppm(image))


def pillow(image, **options):
    out = io.BytesIO()
    image.save(out, "JPEG", **options)
    return out.getvalue()


def djpeg_gray(jpeg):
    return Image.open(io.BytesIO(run("djpeg", "-grayscale", "-pnm", data=jpeg)))


def luma_reference(jpeg):
    image = Image.open(io.BytesIO(jpeg))
    image.load()
    if image.mode == "CMYK":
        # Pillow hands Adobe CMYK back inverted; the file stores 255 for no ink.
        pixels = [tuple(255 - v for v in p) for p in image.getdata()]
        values = [luma(c * k // 255, m * k // 255, y * k // 255) for c, m, y, k in pixels]
    else:
        values = [luma(*p) for p in image.convert("RGB").getdata()]
    gray = Image.new("L", image.size)
    gray.putdata(values)
    return gray


def main():
    qrtool, out = sys.argv[1], pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        image = code_image(qrtool, pathlib.Path(temp))
    gray = image.convert("L")
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 degrees to display.
    exif[0x010F] = "abla-qr fixtures"
    small = image.resize((16, 16))

    fixtures = [
        ("baseline-420-q50.jpg", pillow(image, quality=50, subsampling=2), "gray"),
        ("baseline-420-q90.jpg", pillow(image, quality=90, subsampling=2), "gray"),
        ("baseline-444.jpg", pillow(image, quality=75, subsampling=0), "gray"),
        ("baseline-422.jpg", pillow(image, quality=75, subsampling=1), "gray"),
        ("baseline-411.jpg", cjpeg(image, "-quality", "75", "-sample", "4x1,1x1,1x1"), "gray"),
        ("baseline-gray.jpg", pillow(gray, quality=75), "gray"),
        ("progressive-420.jpg", pillow(image, quality=75, subsampling=2, progressive=True), "gray"),
        ("progressive-444.jpg", cjpeg(image, "-quality", "85", "-sample", "1x1", "-progressive"), "gray"),
        ("progressive-gray.jpg", cjpeg(gray, "-quality", "75", "-progressive"), "gray"),
        ("progressive-restart.jpg", cjpeg(image, "-quality", "75", "-progressive", "-restart", "5B"), "gray"),
        ("restart-420.jpg", cjpeg(image, "-quality", "75", "-optimize", "-restart", "1"), "gray"),
        ("restart-blocks-422.jpg", cjpeg(image, "-quality", "75", "-sample", "2x1", "-restart", "3B"), "gray"),
        ("exif-orientation.jpg", pillow(image, quality=75, exif=exif.tobytes()), "gray"),
        ("extended-16bit-tables.jpg", cjpeg(image, "-quality", "12"), "gray"),
        ("rgb.jpg", cjpeg(image, "-quality", "75", "-rgb"), "luma"),
        ("cmyk.jpg", pillow(image.convert("CMYK"), quality=80), "luma"),
        ("arithmetic.jpg", cjpeg(small, "-arithmetic"), "unsupported_arithmetic"),
        ("precision-12.jpg", cjpeg(small, "-precision", "12"), "unsupported_12_bit"),
        ("lossless.jpg", cjpeg(small, "-lossless", "1"), "unsupported_lossless"),
    ]
    lines = []
    references = {}
    for name, jpeg, kind in fixtures:
        (out / name).write_bytes(jpeg)
        if kind in ("gray", "luma"):
            reference = djpeg_gray(jpeg) if kind == "gray" else luma_reference(jpeg)
            assert reference.size == (WIDTH, HEIGHT), name
            reference_name = references.setdefault(reference.tobytes(), name.replace(".jpg", ".ref.png"))
            if not (out / reference_name).exists():
                reference.save(out / reference_name, optimize=True)
            lines.append(f"{name}\t{reference_name}\t{2 if kind == 'luma' else 0}\t{DATA.encode().hex()}")
        else:
            lines.append(f"{name}\t-\t0\t{kind}")
    (out / "expected.tsv").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
