# Abla QR

Creates and reads QR codes, in plain Abla with no dependencies beyond the
standard library.

```abla
import github("AndreBaltazar8/abla-qr")
import "abla/fs"

fun writeTicket(url: string): bool {
    val matrix = qrEncode(url, QrOptions(errorCorrection = qrEcQuartile)).matrix
    if (matrix == null) return false
    Path("ticket.svg").writeTextAtomic(qrSvg(matrix)) &&
        Path("ticket.png").writeTextAtomic(qrPng(matrix))
}

fun readTicket(png: string): string? = qrReadPng(png).decoded?.data
```

## Creating

`qrEncode(data, options)` takes text or bytes and picks the most compact of
numeric, alphanumeric and byte mode. `qrEncodeBytes` always uses byte mode, and
`qrEncodeSegments` mixes modes by hand. A result has `succeeded`, `error`
(`data_too_long`, `invalid_mask`, ...) and `matrix`.

| `QrOptions` | Default | |
|---|---|---|
| `errorCorrection` | `qrEcMedium` | `qrEcLow`, `qrEcMedium`, `qrEcQuartile`, `qrEcHigh` |
| `minVersion`, `maxVersion` | 1, 40 | the smallest version in the range that fits is used |
| `mask` | -1 | 0 to 7; -1 picks the lowest penalty as the standard describes |
| `boostErrorCorrection` | false | raise the level when the version has room |
| `utf8Eci` | false | mark byte data as UTF-8 with ECI 26 |

Strings hold bytes, so UTF-8 text goes in as it is. Most readers take byte mode to
be UTF-8 without being told. A few don't, and that is what `utf8Eci` is for, but
some older readers trip over the marker.

Output, from a `QrMatrix`:

- `matrix.dark(x, y)`, `matrix.size`, `.version`, `.errorCorrection`, `.mask`, and `qrMatrixText(matrix)`
- `qrSvg(matrix, render)` merges modules into one path, so it has no seams
- `qrPng(matrix, render)` writes a one-bit PNG

`QrRenderOptions` sets `scale` (default 8), `border` (default 4, the quiet zone the
standard asks for), `darkColor` and `lightColor` as `0xRRGGBB`, and
`transparentBackground`.

## Reading

| Function | |
|---|---|
| `qrReadPng(bytes)` | one code from a PNG file's bytes |
| `qrRead(image)` | one code from a `QrImage` |
| `qrReadAll(image)` | every code it finds |
| `qrPngDecode(bytes, maxPixels)` | PNG to `QrImage`: any colour type or depth, Adam7, transparency |
| `qrImageFromBytes(width, height, channels, data)` | raw gray, gray and alpha, RGB or RGBA to `QrImage` |
| `qrDecodeMatrix(matrix)` | when you already have the modules |

A `QrReadResult` has `succeeded`, `error` (`not_found`, `undecodable` or a PNG
error), `decoded` and `corners`, the code's four corners in the image. `decoded`
is a `QrDecoded`: `data`, `version`, `errorCorrection`, `mask`, `segments`,
`correctedErrors` and `mirrored`.

The reader tries a global threshold, then local thresholds for uneven light, then
blurred versions for noise, then inverted colours. It finds finder patterns by
their 1:1:3:1:1 runs, fits a perspective transform to the known patterns and, for
bent codes, corrects it locally from the alignment patterns. Reed-Solomon repairs
what remains. Numeric, alphanumeric, byte, Kanji, ECI, FNC1 and structured-append
symbols all read. Kanji comes out as its Shift JIS bytes, and non-UTF-8 ECI data
as stored: `segments[i].eci` says which.

Malformed files and images return errors. The PNG decoder treats every length as
untrusted and the reader bounds its work, about ten seconds at worst on a 12
megapixel image of pure noise on the machine it was measured on.

### Limits

- **No JPEG.** The reader takes PNG or pixels. To read a JPEG, decode it first and
  pass the pixels to `qrImageFromBytes`.
- All three finder patterns must be found, though each can lose part of itself. A
  code with a finder wholly covered won't be located.
- A code bowed by more than about 2.5 modules fails. ZXing reads somewhat more.
- No Micro QR, and no creation of Kanji segments.
- Structured-append symbols read one at a time. Nothing joins them.

## Tests

`make test` builds the examples and runs the unit tests: tables against the
standard, Reed-Solomon, the matrix of the standard's Annex I, PNG, rendering, and
reader tests on images the tests warp themselves. They include noise fuzzing
against panics.

`make interop` checks against independent implementations, from Nix:

- Module matrices equal another encoder's, bit for bit, for all 160 versions and
  levels (segno for alphanumeric, python-qrcode for byte) and every mask on nine versions.
- zbar and ZXing read all 160 from PNG, and zbar from SVG.
- The reader reads codes made by python-qrcode, segno and qrencode, including
  Kanji, ECI and structured append.
- It reads 160 **synthesized** images, with 28 harder ones measured but not required (`tools/make_fixtures.py`): rotation,
  perspective, skew, curved paper, blur, noise, uneven light, JPEG artifacts,
  damage. These imitate photographs but aren't photographs, and no real camera
  shots are in the suite. A table compares zbar and ZXing on the same images.

## License

Mozilla Public License 2.0. See [LICENSE](LICENSE).
