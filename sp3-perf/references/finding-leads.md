# Finding leads from profiles

A lead is a place where Firefox spends time that it might not need to spend.
The cheapest source of leads is a pair of Speedometer 3 profiles: Firefox and
another engine (WebKit or Chromium), same machine, same iteration count.

## Getting the profiles

- Someone may already have a comparison report: a `profiler.firefox.com`
  "compare-benchmark" page with two `profiles[]=` URLs. Take the two
  `profiler.firefox.com/public/...` links out of it and load them with
  `profiler-cli`; the report page itself is too heavy to drive from a headless
  browser.
- To record your own Firefox profile, use the `profile-capture` skill. For
  WebKit or Chromium, `samply` records a native profile that the Firefox
  Profiler can load. Record the content process main thread, 250 µs interval,
  with symbols.
- Note what the profiled Firefox build was (revision or date). Costs seen in an
  old build may already be fixed.

## Restrict everything to scored time

Speedometer 3 emits a marker per measured step, named `<suite>.<step>-sync` and
`<suite>.<step>-async`. Only samples inside those markers count toward the
score; page setup, suite preparation and idle time between steps do not.

```
profiler-cli load <firefox profile url> --session <you>-fx
profiler-cli load <other profile url> --session <you>-other
profiler-cli filter push --during-marker --search sync --session <you>-fx
profiler-cli filter push --during-marker --search sync --session <you>-other
```

`sync` matches both `-sync` and `-async` and nothing else. Use your own session
names, pass `--session` on every command, and stop your sessions at the end.
Read `profiler-cli guide` once; the rest of this file assumes it.

Total scored samples of each profile (`thread functions --json --limit 0`, sum
of `selfSamples`) give the denominator: a lead of N samples is worth
N / total of the Firefox score time, at most.

## Compare like for like

Function names do not line up across engines, inlining differs, and each
engine attributes shared work (a layout flush, a script callback) to a
different caller. Three comparisons are reliable:

1. **DOM API entry points.** Both engines enter the DOM through generated
   binding functions named after the interface member. Dump both function
   lists and run `scripts/profile_dom_api_diff.py`:

   ```
   profiler-cli thread functions --json --limit 0 --session <you>-fx > fx.json
   profiler-cli thread functions --json --limit 0 --session <you>-other > other.json
   python3 scripts/profile_dom_api_diff.py fx.json other.json
   ```

   The totals include everything the call runs. `click()` and `dispatchEvent()`
   are mostly the script they call back; `getBoundingClientRect`, `offsetWidth`
   and friends are mostly the style and layout flush they force.

2. **Subsystem unions.** "All samples with a style or layout flush on the
   stack" in each engine: `--includes-function` with the handles of the
   relevant roots (`scripts/profile_sum.sh` prints the sum). In Gecko:
   `RestyleManager::ProcessPendingRestyles`, `PresShell::DoFlushLayout`. In
   WebKit: `Document::updateStyleIfNeeded`, `Document::resolveStyle`,
   `Document::updateLayout`, `LocalFrameView::layout`.

3. **A subtree minus what it calls back.** Event dispatch overhead is "inside
   `EventDispatcher::Dispatch` but not inside the listener call":
   `--includes-function <dispatch> --excludes-function <listener call>`. Check
   that the exclusion removes the same things on both sides. A real example:
   Firefox's 2310 samples against WebKit's 1432 looked like an 878-sample gap,
   but the Firefox side still contained `on*` handler script, per-listener
   call setup and front-end (chrome) listeners that the WebKit filter had
   dropped; like for like it was 1695 against 1432.

## Per-suite split

`--during-marker --search <suite>` cannot be combined with the functions query
in one call. For a per-suite breakdown, save the profile
(`profiler-cli profile save`, outside the repository) and compute sample sets
per marker interval in Python, or push a second sticky filter on a private
session.

A lead concentrated in one or two suites is good news: a suite-level local A/B
can see it. A lead smeared over all suites needs try.

## Traps

- **Self time on tiny accessors is not their cost.** `nsWrapperCache::HasFlag`,
  `nsINode::HasSlots`, a refcount flag test: hundreds of self samples on a
  one-instruction function are a cache miss on freshly allocated memory,
  charged to whoever touches it first. Read the function before theorising. A
  flag test that looked like a slow thread-local read was exactly this.
- **Sample counts are upper bounds.** Sampling skid and inlining move samples
  between neighbouring frames. A patch estimated at 670 samples from the
  profile measured as nothing; another estimated at 1.9% of the run measured as
  20% of two suites.
- **The other engine may be faster because the benchmark repeats itself.**
  WebKit caches text break positions keyed on the string and matched
  declarations across flushes; Speedometer sets the same strings and toggles
  the same elements every iteration. That is still a lead, but it is a cache
  to build, not an inefficiency to remove.
- **Front-end code runs in content too.** Chrome listeners (form autofill
  focus handlers, JSWindowActor creation) showed up inside scored steps. They
  are real cost with different owners.
- **Check whether Firefox is already ahead.** Node removal, wrapper creation
  and several DOM calls were cheaper in Firefox than in WebKit. List these
  too; they stop people from optimising the wrong thing.

## Turning a lead into a hypothesis

For each lead, before any patch:

1. Bottom-up on the hot function to see who calls it and from which script
   (JS frames carry source URLs, which tells you the suite and the library).
2. Read the current source of every frame involved. Confirm the frame still
   exists and still does what the profile suggests.
3. Search Bugzilla for the function and the idea. Much of this ground has
   been walked; an existing bug with a work-in-progress patch changes the
   plan from "write it" to "measure theirs and post numbers".
4. Write down the observation (sample counts), the hypothesis (labelled as
   such) and the cheapest experiment that would confirm or kill it.
