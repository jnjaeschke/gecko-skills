# Case studies

Two investigations this skill was distilled from. Read the one closest to
your task for calibration: what the numbers looked like, what went wrong, and
which ideas died.

## 1. innerHTML fast path (bug 1821615), autumn 2026

A small tokenizer for a safe HTML subset that builds DOM directly and falls
back to the full parser. Landed, enabled on Nightly.

What the measurements looked like:

- First estimate: `innerHTML` is 56% of the TodoMVC-jQuery suite but about 7%
  of all scored time. A prototype made `innerHTML` 6 to 9% faster on that
  markup, estimated +0.2% on the score. That was worth pursuing.
- Final stack on try (20 rebuilds, four platforms): score +0.8 to +1.3%, all
  significant; TodoMVC-jQuery +7 to +9%.
- Local opt A/B overstated it about five times: jQuery −19% locally, −3% under
  PGO for the same change.

What went wrong, and what it taught:

- **PGO reversed a design.** The two-pass version was neutral locally and made
  jQuery 2.5 to 4.4% slower on try; the single-pass version fixed it. Later a
  rewrite lost 4.4% on Mac jQuery only. The cause was one of several
  differences in the rewrite (per-text-run SIMD calls instead of one
  whole-input pre-scan). Because the rewrite changed several things at once,
  it took three more pushes to isolate. Change one thing per push.
- **Fake wins from machine state.** Unpinned runs right after a build showed a
  2x improvement that vanished when the baseline was rerun. Hence archived
  binaries and interleaving.
- **Baseline drift.** Small patches compared against a week-old baseline push
  all showed +0.3%; so did unrelated suites. Re-pushed on a fresh shared base,
  only one of four had a signal.
- **Lost pushes.** Five pushes died in shippable builds on warnings, MSVC
  differences or a static-analysis rule; one whole platform expired unstarted.
- **Statistics.** perfcompare's 100 values per side were 20 jobs repeated five
  times; early intervals were twice too narrow.

Ideas that were measured and dropped (do not rediscover them):

- Pooling or eagerly freeing DOM node memory: kernel time is under 5% of the
  content process; several earlier attempts by others also showed nothing.
- Calling deferred deletion per operation: walks the whole purple buffer,
  quadratic.
- SIMD scanning in general: scanning is under 0.5% of the benchmark.
- Batched frame teardown, deferring child removal: about 1% at most, and
  unbinding has to be synchronous.
- A start-tag token cache in the full parser: faster on its micro-benchmark,
  net zero on the score once the fast path exists.
- Hoisting the per-element script blocker in the parser: it is nested inside
  the document update's blocker, so nothing is saved.
- A Rust tokenizer: parity at best, slightly slower on try.

Method that held up: one micro-benchmark per change on real page fragments
(target cases, already-fast guard cases, still-rejected guard cases), a
same-binary pref A/B, a differential test comparing fast path and full parser
on thousands of inputs plus a fuzzer, and PGO verification only at the end,
per group of commits that belong together.

## 2. Firefox versus WebKit profile comparison, November 2026

Two Speedometer 3 profiles (50 iterations each) compared with `profiler-cli`.
Scored time: Firefox 31.9 s, WebKit 29.5 s.

How it ran:

1. Restricted both profiles to step markers, compared DOM binding entry
   points and subsystem unions, and wrote one short case file per lead:
   observation with function handles and sample counts, hypotheses labelled
   as such, first steps.
2. One agent per case investigated in parallel without touching the checkout
   (patches produced from scratch copies), reporting patch files, upper-bound
   savings and unverified points.
3. Reviewed patches were committed as a stack, built once, measured locally
   on the affected suites, and pushed to try (perf on three platforms, tests
   on Linux debug).

What came out:

- The DOM gap was small. Seven DOM leads produced eight small patches with
  profile estimates of 0.04 to 0.37% each. Locally only TodoMVC-jQuery moved
  (−3.3%); the rest needed try.
- The first gap estimate for event dispatch (878 samples) shrank to 263 once
  both engines were filtered the same way.
- A hypothesis from a function name was wrong: a hot "is on main thread"
  helper was a flag test, not a thread-local read. Reading the source took
  one minute.
- The biggest lead was outside DOM and far bigger than its profile estimate:
  the NewsSite suites click a dropdown 50 times and call
  `body.getBoundingClientRect()` after each click. Firefox reflowed every
  time; WebKit skips layout when only an unrelated absolutely positioned
  subtree is dirty. An unsound ceiling pref measured −20 to −24% on both
  suites; a prototype that skips only in provably unaffected cases reached
  about 90% of that, with zero mismatches in a verify mode.
- Two of WebKit's leads were caches that pay off because the benchmark
  repeats itself (text break positions per string, matched declarations
  across flushes).
- A profile-estimated 670-sample style patch showed no effect when measured.

Lessons specific to this shape of work:

- Check for existing bugs before patching layout or style: most leads there
  already had an owner and a work-in-progress patch. The useful contribution
  was numbers for their bug.
- Platform configuration can decide whether an optimisation fires at all.
  The layout skip depended on overlay scrollbars; with classic scrollbars the
  safe condition refuses. That is a reason to measure on every platform
  before believing a local number.
- A load gate that is too strict silently never starts the benchmark. Print
  when a run starts.
