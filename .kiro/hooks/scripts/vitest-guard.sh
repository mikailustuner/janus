#!/usr/bin/env sh
# Runs one vitest file from apps/web and prints a short result for the hook.
# Usage: vitest-guard.sh <hook-name> <test-file relative to apps/web> [-t <test name>]
# Exit 0: pass. Exit 1: fail (findings on stdout and stderr).
set -u
name="$1"; shift
root="$(cd "$(dirname "$0")/../../.." && pwd)"
out="$(pnpm --silent --dir "$root/apps/web" exec vitest --run "$@" 2>&1)"
status=$?
if [ "$status" -eq 0 ]; then
  echo "$name: passed."
  exit 0
fi
# Keep only the useful lines: failing test names and path:line findings.
summary="$(printf '%s\n' "$out" | grep -E '(FAIL|×|apps/[^ ]+:[0-9]+|Expected|Received|^\s+[-+] +"|Error:)' | head -40)"
msg="$name: FAILED
$summary"
echo "$msg"
echo "$msg" >&2
exit 1
