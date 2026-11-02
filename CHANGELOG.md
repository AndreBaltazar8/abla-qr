# Changelog

## Unreleased

- Read QR codes from JPEG files: `qrJpegDecode`, `qrReadJpeg`, and
  `qrReadImageFile`, which tells PNG from JPEG. Baseline, extended sequential and
  progressive Huffman-coded files with any sampling factors and restart
  intervals; gray, YCbCr, RGB and Adobe CMYK or YCCK. Arithmetic coding, 12-bit,
  lossless and hierarchical files are refused.

## 0.1.0

- Create QR codes: versions 1 to 40, all levels, numeric, alphanumeric and byte
  modes, ECI, all masks with automatic selection, module matrix, SVG and PNG.
- Read QR codes from PNG files and pixel data: rotation, perspective, skew,
  curved paper, uneven light, noise and damage; mirrored and inverted codes;
  several codes in one image.
