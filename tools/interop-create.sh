#!/usr/bin/env bash
# The codes qrtool creates, read by an independent reader: zbar must read the PNG and the SVG (rendered by rsvg-convert) of every
# version at every level (160 codes, the largest payload each holds, written by build/interop-payloads from
# tests/reference/matrices.tsv.z). The module matrices are compared with other encoders in tests/reference_test.ab. ZXing, which
# this check once also ran, has no command line tool in nixpkgs and is not run any more.
#   tools/interop-create.sh build/qrtool build/interop-payloads     (inside tools/interop-shell.nix: zbar and librsvg)
set -euo pipefail
qrtool=$1
payloads=$2
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
hex() { od -An -tx1 -v | tr -d ' \n'; }
trim() { local s=$1; while [ "${s: -2}" = 0a ]; do s=${s:0:${#s}-2}; done; printf '%s' "$s"; }
reads() { # $1 = image, $2 = payload file: whether zbar reads exactly the payload (a trailing newline does not count)
    local got want
    got=$(trim "$(zbarimg -q --raw -Sbinary --oneshot "$1" 2>/dev/null | hex)")
    want=$(trim "$(hex < "$2")")
    [ -n "$want" ] && [ "$got" = "$want" ]
}
failures=0 png=0 svg=0
for version in $(seq 1 40); do
    for level in L M Q H; do
        data="$payloads/v$version-$level.bin"
        "$qrtool" encode --ec "$level" --version "$version" --file "$data" --scale 4 --format png --out "$work/code.png"
        "$qrtool" encode --ec "$level" --version "$version" --file "$data" --scale 4 --format svg --out "$work/code.svg"
        if reads "$work/code.png" "$data"; then png=$((png + 1)); else echo "FAIL zbar png v$version-$level"; failures=$((failures + 1)); fi
        rsvg-convert -o "$work/svg.png" "$work/code.svg"
        if reads "$work/svg.png" "$data"; then svg=$((svg + 1)); else echo "FAIL zbar svg v$version-$level"; failures=$((failures + 1)); fi
    done
done
echo "zbar read png: $png/160, zbar read svg: $svg/160"
echo "$failures failures"
[ "$failures" = 0 ]
