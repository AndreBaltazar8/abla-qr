#!/usr/bin/env bash
# Runs qrtool's reader over fixture directories (each has a manifest.tsv of `file<TAB>category<TAB>hex of the data`):
#
#   interop-read.sh QRTOOL "DIR [DIR...]" [CATEGORY=N ...]
#
# Prints a table by category and, for scale, how zbar does on the same images. Exits non-zero when abla-qr misses more
# fixtures of a category than CATEGORY=N allows or, worse, returns wrong data.
set -euo pipefail
qrtool=$1
directories=$2
shift 2
hex() { od -An -tx1 -v | tr -d ' \n'; }
trim() { local s=$1; while [ "${s: -2}" = 0a ]; do s=${s:0:${#s}-2}; done; printf '%s' "$s"; }
declare -A total ours zbar missed allowed
for argument in "$@"; do allowed[${argument%%=*}]=${argument#*=}; done
wrong=0
for directory in $directories; do
    while IFS=$'\t' read -r name category expected; do
        [ -n "$name" ] || continue
        path="$directory/$name"
        total[$category]=$(( ${total[$category]:-0} + 1 ))
        status=0
        got=$(timeout 120 "$qrtool" decode "$path" 2>/dev/null | hex) || status=$?
        if [ "$status" = 0 ] && [ "$got" = "$expected" ]; then
            ours[$category]=$(( ${ours[$category]:-0} + 1 ))
        else
            missed[$category]="${missed[$category]:-} $name"
            if [ "$status" = 0 ]; then wrong=$((wrong + 1)); echo "WRONG DATA $name"; fi
            if [ "$status" != 0 ] && [ "$status" != 1 ]; then echo "CRASH $name: $status"; fi
        fi
        seen=$(trim "$(zbarimg -q --raw -Sbinary --oneshot "$path" 2>/dev/null | hex)" || true)
        if [ "$seen" = "$(trim "$expected")" ] && [ -n "$seen" ]; then zbar[$category]=$(( ${zbar[$category]:-0} + 1 )); fi
    done < "$directory/manifest.tsv"
done
failed=$([ "$wrong" -gt 0 ] && echo 1 || echo 0)
printf '%-20s %5s %8s %5s\n' category total abla-qr zbar
sum_total=0 sum_ours=0 sum_zbar=0
for category in $(printf '%s\n' "${!total[@]}" | sort); do
    printf '%-20s %5d %8d %5d %s\n' "$category" "${total[$category]}" "${ours[$category]:-0}" "${zbar[$category]:-0}" "${missed[$category]:-}"
    if [ $(( ${total[$category]} - ${ours[$category]:-0} )) -gt "${allowed[$category]:-0}" ]; then failed=1; fi
    sum_total=$((sum_total + ${total[$category]})); sum_ours=$((sum_ours + ${ours[$category]:-0})); sum_zbar=$((sum_zbar + ${zbar[$category]:-0}))
done
printf '%-20s %5d %8d %5d\n' all "$sum_total" "$sum_ours" "$sum_zbar"
exit "$failed"
