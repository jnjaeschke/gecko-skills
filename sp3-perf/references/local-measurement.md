# Measuring locally

Local runs answer one question: is there an effect worth spending try
capacity on, and in which suites? They do not produce the number that goes
into the bug; try does.

## Build configuration

Measure only on an optimised, non-debug build. A mozconfig along these lines,
with its own objdir so it coexists with your debug build:

```
mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/obj-opt
ac_add_options --enable-optimize
ac_add_options --disable-debug
ac_add_options --enable-profiling
```

`--enable-debug` builds carry assertions and refcount logging that inflate
exactly the paths DOM work touches; their profiles and timings are not
representative. Do not build a debug or assertion-enabled variant "for tests"
before there is a measured win: it costs a near-full build and tells you
nothing about performance. Mention unexercised assertions in a sentence and
leave correctness runs for after the numbers, or for the try test push.

Pass the mozconfig explicitly (`MOZCONFIG=... ./mach build`) and confirm the
objdir in the build log. Always do a full `./mach build`; partial build
commands leave stale pieces. One build per objdir at a time.

A build that exits 0 has not necessarily recompiled your file (a compiler
cache can mask it). Check that the binary changed: compare `libxul` between
the archived baseline and the new build, or look for your file in the log.

## Archive binaries, then interleave

Never compare a run from now with a run from earlier. Machine state moves
whole runs by large factors: the same binary measured 3240 ms right after a
build and 1520 ms later, which would have read as a 2x win for whatever patch
happened to be measured second.

1. Build the baseline, `scripts/archive_bin.sh <objdir> bins/base`.
2. Apply the change, build, `scripts/archive_bin.sh <objdir> bins/patch`.
3. Run all configurations interleaved with `scripts/sp3_ab.py`.
4. `scripts/sp3_ab_stats.py` on the result file(s).

Prefer a pref over a second binary whenever the change can be gated: the same
binary with the pref on and off removes code-layout differences between
builds from the comparison. Keep the pref for the try push too.

## What to run

- Start with the suites the lead lives in, not the whole benchmark. Four to
  six suites, 6 to 10 rounds, 8 iterations take about five to ten minutes and
  resolve effects of a few percent per suite.
- Full Speedometer 3 locally costs several minutes per launch, and its score
  interval ends up around ±1.5 to 3% after an hour. A stack whose summed
  estimate is under 1% will not separate from baseline locally. Do not burn an
  hour to learn that; push to try.
- Say how long a run will take before starting it, and ask first if it is
  more than about ten minutes on a machine someone is working on.
- Wait for the machine to settle after a build. `sp3_ab.py` prints the load
  average at start and end; a run that started at load 14 is not evidence.

## Know the noise floor

Include a pair of configurations that cannot differ: the same binary twice, or
the same binary with a pref that the suites under test never reach. Their
"delta" is the noise floor of this run. In one 4-round run, two identical
configurations differed by 3 to 4% on three suites; every other number of that
size in the table was meaningless, and only the 20% effects were results.

If two configurations that should agree disagree with an interval excluding
zero, add rounds before interpreting anything.

## Upper bounds without building the feature

Before designing a careful optimisation, measure what it could be worth at
most with a deliberately wrong shortcut behind a pref: skip the work
unconditionally, return a stale value, hard-code the fast path. It must never
land, and the commit message should say so, but it answers "is this worth a
week" in one build. An unsound "skip the layout flush in
`body.getBoundingClientRect()`" pref showed 20 to 24% on two suites; the
sound prototype then reached about 90% of that ceiling, and the ceiling pref
was deleted.

Pair any prototype that skips work with a verification mode: a second pref
that also does the full work and logs when the results differ. Zero
mismatches over a benchmark run is weak evidence, but a single mismatch is
proof of a bug.

The opposite shortcut also exists: edit a local copy of the benchmark to drop
the call that triggers the work. It needs no build, but it usually removes
more than the engine could ever skip, so treat it as a looser bound.

## Micro-benchmarks

For a single operation (one DOM call, one parser path) a page that repeats it
and reports times is faster to iterate on than Speedometer suites. Rules:

- Drive it the same way: archived binaries, interleaved launches, many
  samples, bootstrap interval. A harness that reports whole milliseconds on a
  90 ms loop has a resolution of 1.1%; two configurations one step apart are
  not different.
- Instruction counts (`perf stat -e instructions:u`) are far less noisy than
  time for "did this remove work" questions.
- Back-to-back loops fault on fresh memory in ways the real benchmark does
  not; a win that only appears in a tight loop may be an artefact.
- Local non-PGO results overstate PGO results. A fast path that was 19%
  faster on its suite locally was 3% faster in shippable builds. Use local
  numbers for ranking and go/no-go, not for claims.

## What to report from a local run

The table from `sp3_ab_stats.py`, the number of rounds, the load average, the
noise-floor pair, and one sentence per configuration saying whether it
separated from the baseline. Report "not resolved" as that, not as "no
effect".
