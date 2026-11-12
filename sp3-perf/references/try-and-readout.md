# Try pushes and reading them out

Shippable builds on try are PGO builds on reference hardware. They are the
only measurement that predicts what lands, and the only one that resolves
effects below about 1%.

## Before pushing

- **Push only what you intend to measure.** If the branch carries experiments
  on top, check out the commit to measure (detached) and push from there, then
  return to the branch. To isolate one change inside a stack, push the stack
  with and without it rather than reasoning about it afterwards.
- **Warnings are errors in shippable builds.** Search the local build log for
  `warning:` in every file you changed; it must be empty. Pushes have been
  lost to an unused variable that only exists without refcount logging, to
  `%u` with a `size_t`, to `auto*` bound to a `std::array` iterator (MSVC), to
  `reinterpret_cast` from `char16ptr_t` (a class on Windows), and to a static
  analysis rule (`aRv.Throw()` not followed by `return`).
- **Build the exact push content locally once** if it differs from what you
  last built. A broken push costs hours of scarce Mac and Windows hardware.
- **Flip prefs in a separate, clearly named try-only commit** on top
  ("Try only: enable ..."), so the measured code is the reviewable code.
- Check the push list before retrying a `mach try` that printed an error: it
  may have pushed anyway.

## The perf push

```
./mach try perf -q speedometer3 --platforms desktop --rebuild 20
```

- This pushes two revisions: the base (your commits removed) and the new one.
  The output prints both Treeherder links and a perf.compare link.
- `--rebuild 20` is the useful setting: about ±0.2% on the score and ±0.3 to
  0.5% per suite. Fewer rebuilds cannot see sub-1% changes.
- `--platforms desktop` is Linux, Windows and macOS. Linux alone is cheaper
  and faster, but its results are the least stable of the three; Windows and
  Mac numbers are the ones people trust, and Mac capacity is the scarcest.
  Agree on platforms with whoever owns the work instead of defaulting.
- When a base push for the same base commit already exists, add
  `--single-run` and compare against it. Several stacks on one base then
  share one baseline, and each pair of pushes isolates one change.
- One push per question. Write down, per push: the Lando ID, the local
  commit, what it contains, what it is compared against, and what you expect.
  Without that record nobody can read the results a week later.

## The test push

A perf push runs no tests. Alongside it, push tests for the touched areas:
Linux only unless a change is platform-specific, debug builds (the risk in
perf patches is assertions and behaviour, not opt-only code), selected by
path so only relevant chunks run. Show the selection to the person you are
working for before pushing; `./mach try fuzzy --no-push ...` prints it.

```
./mach try fuzzy \
  -q "'test-linux2404-64/debug-mochitest-plain- !gpu !headless !http2 !http3 !nofis !standalone !xorig !swr" \
  -q "'test-linux2404-64/debug-web-platform-tests- !canvas !crashtest !eme !nofis !pb !reftest !webcodecs !webgpu !webrtc" \
  dom/events dom/base/test testing/web-platform/tests/dom
```

Task names change over time; dry-run and adjust. Do not use `mach try auto`
for this: it selects far more than the question needs.

## Reading the results

```
python3 scripts/perfcompare.py <base revision> <new revision> --save cmp.json
```

Revisions are the full try revisions of the two pushes (Treeherder push page,
or `treeherder-cli <lando id> --match-filter all`). The script prints, per
platform, score and per-suite change with a bootstrap interval, positive =
better.

How to read the table:

- **One value per job.** The API repeats each job's value per replicate, so 20
  jobs look like 100 samples and naive intervals come out about twice too
  narrow. The script deduplicates; if you compute anything yourself, do the
  same.
- **Medians, not means.** A few slow jobs produce fake 5 to 12% "changes" in
  means.
- **The same sign on several platforms is the signal.** A lone significant
  move on one platform, especially on a suite the patch cannot touch, is
  usually PGO or code-layout variance. Unrelated suites drifting by 0.7 to
  1.6% together means the baseline is stale or the base differs.
- **Check n.** `n=20/13` means jobs are missing; Windows hardware and Mac
  profile-generation jobs sometimes expire unstarted. No data is not "no
  change".
- **Results arrive platform by platform**, reference hardware last. Do not
  conclude from Linux alone.
- **PGO can reverse a local result.** A fast path that was clearly faster
  locally made its suite 2.5 to 4.4% slower in shippable builds until its
  structure changed. When local and try disagree, try is right; download the
  shippable binaries and A/B those locally to investigate.

## Where the numbers go

Measurements, tables and try links go into the Bugzilla bug as comments.
Commit messages describe what the code does and why it is correct; they
outlive the measurements and the links.

Keep each measurable change in its own commit, so each try comparison is
attributable. A small change that showed nothing on its own should not ride
along claiming part of a neighbour's win.
