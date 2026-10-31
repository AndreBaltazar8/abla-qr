# Test fixtures

`photo-style/` holds **synthesized images, not photographs**. Each is a code from
another encoder (python-qrcode, segno or qrencode) that `tools/make_fixtures.py`
put through imitations of what a camera does: rotation, perspective, blur, sensor
noise, uneven light, JPEG artifacts, curved paper, damage. `manifest.tsv` lists
`file`, `category` and the expected data in hex.

`png/` holds small images written byte by byte by `tools/make_png_fixtures.py`, one
for each PNG colour type, depth and interlacing. `expected.txt` lists their gray
values.

`make fixtures` regenerates both.
