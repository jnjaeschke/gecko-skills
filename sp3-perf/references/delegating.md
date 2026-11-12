# Fanning leads out to subagents

Several independent leads can be investigated in parallel. What makes it work
is that a subagent cannot corrupt the one checkout and objdir everyone shares.

## One case file per lead

Write a directory outside version control with a README and one file per
lead. The README holds what every case needs: profile links, how to load them
with the step-marker filter, the scored-time totals, the limits of the
comparison, and the working rules. Each case file holds:

- **Observation**: function handles and sample counts for both engines, and
  the exact command that reproduces them.
- **Hypotheses**, each labelled unverified.
- **Prior work** to read first: bugs, branches, earlier dead ends.
- **First steps**, starting with "confirm this on the current source".

A case file must stand alone: the agent reading it has none of your context.

## Brief for an investigating agent

- Goal and what counts as a result. Say that "nothing worth patching",
  "already tracked in bug N" and "the estimate was wrong" are valid results;
  otherwise agents manufacture a patch.
- No edits inside the checkout, no state-changing git, no builds, no tests,
  no browser. Patches are produced from scratch copies: copy each file to
  `a/<path>` and `b/<path>` in a temp directory, edit `b`, `diff -u`, fix the
  headers, and verify with `git apply --check` against the checkout. One
  logical change per patch file.
- Profile access through shared, already-loaded `profiler-cli` sessions,
  ephemeral flags only: no `filter push`, `zoom`, `thread select`, `stop` or
  `load`. Fourteen agents each loading two 50 MB profiles is a waste.
- Every claim carries a cited function or file, a sample count, or the word
  "unverified". Never assert another engine's behaviour without reading its
  source.
- Required output: a findings file, patch files, and a short final report
  listing patches with upper-bound savings, risks and unverified points.

For code outside the requester's own area (layout, style, graphics), ask for
a plain-language note on the concept each patch relies on, and for the exact
condition under which any skipped work is safe.

## Integrating

Read every patch before committing it; agents cannot compile, so expect the
first build to find errors. Commit one patch per commit, build once at the
tip, then measure. Hold back anything that changes behaviour or a heuristic
until its owner has seen it, and anything whose effect depends on an
unverified hit rate.

Only one agent at a time may build or benchmark, and nothing else should
build while a benchmark runs. A prototype that needs build-measure-fix loops
goes to a single agent with the checkout to itself, an explicit build
command, an explicit benchmark command, and a list of what it must not do
(other build variants, test suites, try pushes, branch surgery).
