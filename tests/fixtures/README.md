# Test fixtures

`photo-style/` holds **synthesized images, not photographs**. Each is a code from
another encoder (python-qrcode, segno or qrencode) that `tools/make_fixtures.py`
put through imitations of what a camera does: rotation, perspective, blur, sensor
noise, uneven light, JPEG artifacts, curved paper, damage. `manifest.tsv` lists
`file`, `category` and the expected data in hex.

`png/` holds small images written byte by byte by `tools/make_png_fixtures.py`, one
for each PNG colour type, depth and interlacing. `expected.txt` lists their gray
values.

`jpeg/` holds JPEG files of one code from this library's encoder, written by
Pillow and libjpeg-turbo's cjpeg by `tools/make_jpeg_fixtures.py`, one for each
layout: sampling factors, progressive, restart markers, quality, EXIF, RGB, CMYK,
and three the decoder refuses. `*.ref.png` is the gray libjpeg makes of them, and
`expected.tsv` lists `file`, reference, tolerance and the code's data in hex (or
the error).

`make fixtures` regenerates all three, with `build/qrtool` from `make examples`.
