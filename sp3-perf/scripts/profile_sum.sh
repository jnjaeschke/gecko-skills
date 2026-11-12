#!/bin/bash
# Sum the samples a profiler-cli filter selects and list the top functions.
#
#   profile_sum.sh <session> <label> <topN> [profiler-cli filter flags...]
#
# Examples (f-N are function handles from `profiler-cli thread functions`):
#   profile_sum.sh fx "dispatch minus JS" 30 --includes-function f-5714 --excludes-function f-5448
#   profile_sum.sh fx "setAttribute subtree" 30 --root-at f-4884
#
# The total is the number of samples matching the filter; with a 250 us
# sampling interval, 4 samples are 1 ms. Uses only ephemeral flags, so it never
# changes the session's sticky filters and is safe on a shared session.
set -euo pipefail
session=$1
label=$2
top=$3
shift 3
out=$(mktemp)
trap 'rm -f "$out"' EXIT
profiler-cli thread functions --json --limit 0 --session "$session" "$@" > "$out"
python3 - "$out" "$label" "$top" <<'PY'
import json, sys
functions = json.load(open(sys.argv[1]))["functions"]
top = int(sys.argv[3])
print("###", sys.argv[2], "| samples:", sum(f["selfSamples"] for f in functions))
for title, key in (("self", "selfSamples"), ("total", "totalSamples")):
    print(f"-- top by {title} (self total handle name)")
    for f in sorted(functions, key=lambda f: -f[key])[:top]:
        print("   ", f["selfSamples"], f["totalSamples"], f["functionHandle"], f["name"][:110])
PY
