#!/bin/sh
set -eu

test_root="$(mktemp -d "${TMPDIR:-/tmp}/rvt-test.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT INT TERM

# Tests that inject guard fixtures need a writable checkout. The production
# source remains root-owned and immutable at /opt/rvt.
cp -R --no-preserve=ownership,mode /opt/rvt/. "$test_root"
cd "$test_root"
python -m pytest "$@"
