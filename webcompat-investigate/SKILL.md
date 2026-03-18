---
name: webcompat-investigate
description: Investigate webcompat bugs by reproducing in Firefox and Chrome, comparing behavior, checking specs, profiling, and producing a structured investigation document with root cause analysis and lessons learned.
argument-hint: "<bug-number-or-url> [optional: investigation-dir]"
---

# Webcompat Investigation

**Bug**: $0
**Investigation directory**: $1 (default: `~/webcompat-investigations`)

You are conducting a structured webcompat investigation. Your goal is to understand
why a website behaves differently in Firefox vs other browsers, determine whether
this is a Gecko bug or expected behavior, and if it's a bug, identify the root cause
in Gecko code.

This is a collaborative, pausable workflow. After each phase, present your findings
and ask the engineer before proceeding to the next phase. The engineer may redirect
you at any point.

## Important principles

- Every observation and decision goes into the investigation document
- Distinguish read-only actions from side-effecting ones (see Phase 3)
- When the engineer intervenes or redirects, log their input and rationale
- The goal is not just a fix, but institutional knowledge about what went wrong and why
- Save screenshots as files alongside the investigation document and reference them
  from the markdown (e.g., `![Firefox screenshot](firefox-initial.png)`)

## Phase 0: Setup

1. Create the investigation directory (`{investigation-dir}/bug-{number}/`) if it
   doesn't exist. This directory lives outside the gecko tree.
2. Fetch the bug report using `@moz:bugzilla://bug/{bug_id}` (use the MCP resource)
3. Extract: URL, steps to reproduce (STR), expected behavior, actual behavior
4. Create the investigation document (see template below)
5. Present the bug summary and ask the engineer to confirm the STR before proceeding

## Phase 1: Initial Observation (read-only only)

Perform these actions. They are all safe and have no side effects on the page.

1. Open the URL in Firefox using `navigate_page`
2. Take a screenshot with `screenshot_page` — save it as
   `{investigation-dir}/bug-{number}/firefox-initial.png`
3. Collect console messages with `list_console_messages`
4. Collect network errors with `list_network_requests` (look for failed requests)
5. Snapshot the DOM: `evaluate_script` with `document.documentElement.outerHTML`
   (do this early, before any other JS evaluation)
6. If a Chrome MCP is available, repeat steps 1-4 in Chrome, saving the screenshot
   as `chrome-initial.png`

Record all observations in the investigation document. Present the Firefox vs Chrome
screenshots and any console/network differences. Ask the engineer what they notice
before forming a hypothesis.

## Phase 2: Hypothesis

Based on Phase 1 observations:

1. Identify the area of divergence (layout, rendering, events, API behavior, etc.)
2. Look up the relevant spec using `webspec-index`:

   ```bash
   webspec-index search "FEATURE_NAME" --limit 5
   webspec-index query 'SPEC#section' --format markdown
   ```

3. Determine the normative behavior according to the spec
4. Form a hypothesis: what is Gecko doing wrong (or is Chrome wrong, or is the
   spec ambiguous?)

Record the hypothesis in the document with confidence level (low/medium/high).
Present it to the engineer and ask for their input before proceeding.

## Phase 3: Targeted Investigation

This phase involves JS evaluation that may have side effects. Categorize every
probe before executing it.

### Side-effect categories

**Safe (read-only, no layout/style side effects):**

- `element.getAttribute()`, `element.className`, `element.id`
- `element.childElementCount`, `element.children.length`
- `element.innerHTML` / `element.outerHTML` (reads serialized DOM)
- `document.querySelectorAll()` (returns existing nodes)

**Potentially side-effecting (forces style/layout resolution):**

- `getComputedStyle(element).property` — forces style computation
- `element.offsetHeight`, `element.offsetWidth` — forces layout
- `element.getBoundingClientRect()` — forces layout
- `element.scrollTop`, `element.scrollLeft` — may trigger scroll events

**Definitely side-effecting (avoid during observation):**

- Any DOM mutation (setAttribute, appendChild, etc.)
- Dispatching events
- Changing focus
- Scrolling programmatically

### Investigation procedure

1. **Start with safe probes only.** Often the DOM snapshot + console errors are enough.
2. Log each probe in the investigation document table with its side-effect category.
3. If you need layout/style queries, do them all in a single `evaluate_script` call
   to minimize cascading effects. Note this in the document.
4. If you need to do something side-effecting, **reload the page first** to get a
   clean state, then perform the action.
5. Run the same probes in Chrome for comparison.
6. Save any additional screenshots taken during investigation with descriptive names
   (e.g., `firefox-after-scroll.png`, `chrome-computed-styles.png`).

### Using the profiler

If the hypothesis involves layout, rendering, or performance:

1. Capture a profile during page load or the repro interaction.
   If `profiler-cli` is available:

   ```bash
   # Page load analysis
   profiler-cli --page-load PROFILE_URL_OR_FILE

   # Top markers (layout, style, paint)
   profiler-cli --top-markers PROFILE_URL_OR_FILE

   # Call tree for hot functions
   profiler-cli --calltree 15 PROFILE_URL_OR_FILE

   # Focus on specific marker types
   profiler-cli --focus-marker "Reflow" --calltree 10 PROFILE_URL_OR_FILE

   # Investigate a specific function's callers
   profiler-cli --callers-of "FunctionName" PROFILE_URL_OR_FILE

   # Source-level annotation
   profiler-cli --annotate src "FunctionName" PROFILE_URL_OR_FILE
   ```

   If `profiler-cli` is not available, use `evaluate_chrome_script` to control
   the Gecko profiler directly:

   ```js
   // Start profiling (in chrome context)
   Services.profiler.StartProfiler(1000000, 1, ["default"], ["GeckoMain", "Compositor"]);
   // ... navigate / perform action ...
   // Stop and get data
   let profile = await Services.profiler.getProfileDataAsync();
   ```

2. Record profiler findings in the investigation document.

### Using searchfox for Gecko code

Once you have a hypothesis about which Gecko subsystem is involved:

```bash
# Find the implementation
searchfox-cli --define 'ClassName::MethodName'
searchfox-cli --id ClassName -l 50 --cpp

# Search for spec references
searchfox-cli -q "spec-url#fragment" --only-normal -l 100
```

## Phase 4: Root Cause

By now you should understand the bug. Document:

1. **What Gecko does wrong** — the specific behavior that diverges from the spec
2. **Where in the code** — file, function, line (use searchfox links)
3. **Why it's wrong** — what the spec requires vs what Gecko implements
4. **Why this assumption existed** — historical context, ambiguous spec text,
   edge case not considered, etc.

If you can't determine the root cause, document what you've ruled out and what
avenues remain. Ask the engineer for guidance.

## Phase 5: Synthesize Test Case

Now that you understand the root cause, **synthesize** (don't minimize) a test case:

1. Write a minimal self-contained HTML file that demonstrates the specific bug
2. It should be as small as possible while clearly showing the divergence
3. Load it in Firefox via `navigate_page` and screenshot — confirm it reproduces.
   Save as `firefox-testcase.png`.
4. Load it in Chrome — confirm it behaves correctly there.
   Save as `chrome-testcase.png`.
5. Save the test case as `{investigation-dir}/bug-{number}/testcase.html`

The test case should be understandable on its own — someone reading it should be
able to see what behavior is being tested without reading the investigation doc.

## Phase 6: Lessons Learned

This is the most important section for institutional knowledge. Document:

1. **What wrong assumption did Gecko have?** Be specific about the code/logic.
2. **Why did this assumption exist?** (spec was ambiguous at the time, edge case,
   optimization shortcut, copy-paste from different context, etc.)
3. **What web pattern triggered this?** What did the web developer do that exposed
   the bug? Is this a common pattern? Is it from a framework?
4. **Could we have caught this earlier?** Missing WPT? Missing fuzzing coverage?
   Spec change we didn't track?

## Investigation Document Template

Create this file at `{investigation-dir}/bug-{number}/investigation.md`:

```markdown
# Webcompat Investigation: Bug {number}

## Bug Report
- **URL**: {url}
- **STR**: {steps to reproduce}
- **Expected**: {expected behavior}
- **Actual**: {actual behavior in Firefox}
- **Date**: {today}
- **Engineer**: (name if provided)

## Phase 1: Initial Observation

### Firefox
- Screenshot: ![Firefox](firefox-initial.png)
- Console errors: (list)
- Network errors: (list)

### Chrome
- Screenshot: ![Chrome](chrome-initial.png)
- Console errors: (list)
- Network errors: (list)

### Differences observed
(what is visually or behaviorally different)

## Phase 2: Hypothesis
- **Area**: (layout / rendering / events / API / ...)
- **Hypothesis**: ...
- **Spec reference**: ...
- **Confidence**: low / medium / high

## Phase 3: Targeted Investigation

### Probes performed
| # | Query | Side-effect risk | Result (Firefox) | Result (Chrome) |
|---|-------|-----------------|-------------------|-----------------|
|   |       |                 |                   |                 |

### Page reloads during investigation: 0
### Hypothesis updated: no

### Profiler analysis (if applicable)
- Profile: (URL or file)
- Key markers: ...
- Hot functions: ...

## Phase 4: Root Cause
- **What**: ...
- **Where**: (file:line, searchfox link)
- **Spec says**: ...
- **Gecko does**: ...
- **Why this assumption existed**: ...

## Phase 5: Test Case
- File: [testcase.html](testcase.html)
- Reproduces in Firefox: ![Firefox testcase](firefox-testcase.png) yes/no
- Correct in Chrome: ![Chrome testcase](chrome-testcase.png) yes/no

## Phase 6: Lessons Learned
- **Wrong assumption**: ...
- **Why it existed**: ...
- **Web pattern that triggered it**: ...
- **Could we have caught this earlier?**: ...

## Engineer Interventions
(Log every time the engineer redirected the investigation, with their reasoning)

| When | Engineer said | Action taken |
|------|-------------|--------------|
|      |             |              |
```
