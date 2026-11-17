# Reference matrices

`matrices.tsv.z`: one line per matrix, tab separated: version, error correction level, mode (`alphanumeric` or `byte`), mask,
the payload in hex, and the module matrix as rows of `0`/`1` joined by `/`. 412 lines: every version 1 to 40 at every level
(with the mask that version's number picks) and all 8 masks on versions 1, 2, 6, 7, 14, 21, 27, 32 and 40. Every payload is the
longest the mode allows at that version and level, as segno reports it, so a table error in this library shows as a mismatch.

Made once, on 2026-11-17, by a Python script (`git show 1ecd437:tools/interop_create.py`, with its helpers `capacity`, `payload`
and `reference_rows`; seed 20261031): segno 1.6.6 for the alphanumeric payloads (odd versions) and python-qrcode 8.2 for the byte
payloads (even versions), both with an explicit version, level and mask. `tests/reference_test.ab` encodes the same payloads
and compares the matrices; it runs in `make test`.
