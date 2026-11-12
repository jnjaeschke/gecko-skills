---
name: sp3-perf
description: >
  Speedometer 3 performance work on Firefox/Gecko, end to end: find where time
  goes (including Firefox-versus-WebKit or Chromium profile comparisons), turn
  leads into hypotheses and patches, measure them locally without fooling
  yourself, push to try, and read the results out statistically. Use this
  whenever the task is to make Speedometer 3 (SP3, Speedometer) faster, to
  judge whether a DOM, parser, style or layout change helps or hurts SP3, to
  compare two builds or a pref on SP3 suites, to interpret an SP3 try perf
  comparison, or to plan such work, even when the user only says "is this
  worth it for Speedometer" or "why is WebKit faster here". Not for triaging a
  Perfherder regression alert (perf-regression-triage), for the mechanics of
  other perf harnesses (perftest), for recording a profile (profile-capture)
  or for JS engine shell benchmarking (js-perf-investigation).
---

# Speedometer 3 performance work

Speedometer 3 is mature territory. The remaining wins are mostly small: a
change worth 0.3% of the score is a real win, and a good month is several of
those. Work at that scale fails in two ways: believing an effect that is
noise, and discarding an effect because the measurement could not see it.
Everything below exists to avoid those two.

The loop:

1. **Find leads** in profiles.
2. **Verify** each lead against the current source and existing bugs.
3. **Estimate the ceiling** cheaply before building the real thing.
4. **Measure locally** to rank and to decide go or no-go.
5. **Push to try** for the number that counts.
6. **Read out** with proper statistics, and write it up in the bug.

Scripts are in `scripts/` next to this file; run the Python ones that drive
Firefox with `./mach python` from the checkout root.

## Rules that hold throughout

- **Separate observation from inference.** Sample counts, timings and source
  lines are observations. "Why it is slow" and "what the patch will save" are
  hypotheses until measured. Label them, and say what would confirm them.
- **Never state what code does from its name.** Read it. Never state what
  another engine does without reading its source or its profile.
- **Profile estimates are upper bounds, and often wrong in both directions.**
  They rank leads; they do not size wins.
- **Small is not nothing.** Do not drop an idea because its estimate is under
  1%. Do say when a measurement could not have resolved it.
- **One change per measurement.** Keep each measurable change in its own
  commit, and each try push answering one question.
- **Negative results are results.** "No effect", "already tracked", "estimate
  was wrong" save the next person the same week. Record them.
- **Shared resources are scarce.** One build per objdir at a time, nothing
  else running during a benchmark, few Mac and Windows try pushes, and no
  long local runs on a machine someone is using without asking.
- **Confirm before outward-facing actions.** Show the exact try selection
  before pushing; never submit for review unasked.

## 1. Find leads

Read `references/finding-leads.md`. In short: load the profiles with
`profiler-cli`, restrict both to the benchmark's step markers, and compare
like for like: DOM binding entry points (`scripts/profile_dom_api_diff.py`),
subsystem unions, and subtrees minus their callbacks
(`scripts/profile_sum.sh`). Express every lead as samples and as a share of
scored time. Also list where Firefox is already ahead.

If there is no second engine to compare with, the same method works on a
Firefox profile alone: per-suite time by subsystem, then the hottest DOM
entry points and their callers.

## 2. Verify before patching

For each lead: find the callers and the script that triggers it, read the
current source of every frame, and search Bugzilla. The profiled build may be
old, the hot frame may be an inlined accessor absorbing a cache miss, and
someone may already own the fix. When a bug with a work-in-progress patch
exists, the useful move is usually to measure that patch and post numbers,
not to write a competing one.

Write each surviving lead down as: observation, hypothesis, cheapest
experiment. With several independent leads, fan them out as described in
`references/delegating.md`.

## 3. Estimate the ceiling

If the real fix is more than a small patch, first measure what it could be
worth with a deliberately crude version behind a pref (skip the work, return
the stale value). One build tells you whether the careful version deserves a
week. Delete the crude pref once a real prototype exists, and give any
prototype that skips work a verify mode that does the full work too and logs
differences.

## 4. Measure locally

Read `references/local-measurement.md`. In short:

- Optimised non-debug build only; no assertion-enabled build until there is a
  win to protect.
- Archive each binary (`scripts/archive_bin.sh`) and run all configurations
  interleaved (`scripts/sp3_ab.py`), on the suites the lead lives in. Prefer
  a pref toggle on one binary over two binaries.
- Include two configurations that cannot differ; their delta is the noise
  floor. Get intervals from `scripts/sp3_ab_stats.py`.
- Expect local numbers to overstate what PGO builds will show, by as much as
  five times. Use them to rank and to decide, not to claim.

A typical run:

```
./mach python <skill>/scripts/sp3_ab.py \
    --config base=bins/base/firefox \
    --config patch=bins/patch/firefox \
    --config patch-off=bins/patch/firefox:my.feature.enabled=false \
    --suites NewsSite-Next,NewsSite-Nuxt,TodoMVC-jQuery \
    --rounds 8 --iterations 8 --out ab.json
python3 <skill>/scripts/sp3_ab_stats.py ab.json --pair patch:patch-off
```

Suite names are the ones in the benchmark's own UI (`TodoMVC-jQuery`,
`NewsSite-Next`, `Editor-TipTap`, `React-Stockcharts-SVG`, ...).

## 5. Push to try

Read `references/try-and-readout.md`. In short: check the build log for
warnings in changed files, push only the commits being measured, use
`./mach try perf -q speedometer3 --platforms desktop --rebuild 20` (with
`--single-run` against an existing base push), agree on platforms first, and
pair it with a Linux debug test push selected by path. Record for each push
what it contains, what it is compared against and what you expect.

## 6. Read out and report

`scripts/perfcompare.py <base rev> <new rev>` prints per-platform changes
with intervals, one value per job. Trust a move that has the same sign on
several platforms; distrust a lone significant move on a suite the patch
cannot reach. Missing jobs are missing data, not "no change".

Report in this shape, in the bug (not in commit messages):

```
What changed: <one line per commit>
Local (opt, N rounds, suites ...): <table, noise floor, what separated>
Try (base <rev>, new <rev>, 20 rebuilds): <score and affected suites per platform, with intervals>
Verdict: <win / neutral / regression / not resolved>, and what remains unverified
```

## Calibration

`references/case-studies.md` has two worked investigations with real
numbers: a parser fast path taken from first estimate to landing, and a
Firefox-versus-WebKit comparison that produced a stack of small DOM patches
and one large layout finding. It also lists ideas that were measured and
dropped; check it before proposing node memory pooling, more SIMD scanning or
parser token caches.
