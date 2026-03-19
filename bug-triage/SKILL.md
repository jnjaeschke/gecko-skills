---
name: bug-triage
description: Semi-automatic bug triage. Enriches a Bugzilla bug with context (similar bugs, code pointers, spec situation, crash data), assesses severity/difficulty, and produces a concise markdown summary for an engineer to pick up.
argument-hint: "<bug-number>"
---

# Bug Triage

**Bug**: $0

You are conducting a supervised bug triage. Your goal is to enrich a bug with
context so that it can be efficiently triaged and picked up by an engineer. You
produce a concise markdown document suitable for pasting as a bug comment.

This is a supervised workflow. After each phase, present your findings and ask
the engineer before proceeding to the next phase. The engineer may redirect you
at any point.

## Important principles

- Accuracy above all. Every claim must be backed by a source (searchfox
  permalink, spec URL, crash-stats data, BMO link). Do not guess.
- All searchfox links in the output **must** be permalinks (using a commit
  hash, not `/source/`). Use `searchfox-cli --permalink` to get them.
- Be concise. The output is a bug comment, not a research paper.
- Distinguish between what you know and what you suspect.
- If you cannot determine something, say so rather than speculate.
- When the engineer intervenes or redirects, adjust accordingly.

## Phase 0: Intake

1. Fetch the bug using `@moz:bugzilla://bug/{bug_id}` (MCP resource)
2. Extract key signals:
   - Summary, product, component, status, severity, priority
   - Keywords, flags, whiteboard tags
   - URL (if webcompat), crash signature (if crash), STR
   - Dependencies, blockers, see-also links
3. **Classify the bug type:**
   - **webcompat**: Has a URL, mentions "works in Chrome/Safari", rendering or
     behavior difference
   - **crash**: Has a crash signature or STR describes a crash/hang
   - **feature-behavior**: An API or feature does not work as expected, but no
     specific website is involved
   - **performance**: Slow, janky, high memory usage
   - **other**: Test failures, build issues, infrastructure, etc.
4. Present the classification and a clean summary. Ask the engineer to confirm
   before proceeding.

## Phase 1: Context Gathering

Run these in parallel where possible, based on bug type.

### Always do:

**Search for similar/duplicate bugs:**
```bash
bmo-search similar {bug_id} --limit 10
```

If the similar bugs look relevant, fetch a few to check if this is a known issue
or has been attempted before:
```bash
bmo-search get {related_bug_id}
```

**Find relevant implementation code:**
```bash
# Use keywords from the bug summary/description
searchfox-cli --id RelevantClassName --cpp -l 50
searchfox-cli --define 'ClassName::MethodName'
searchfox-cli -q "relevant search term" --path "relevant/directory" -l 50

# When you need a link for the output document, use --permalink:
searchfox-cli --define 'ClassName::MethodName' --permalink
```

**Check the spec situation (if applicable):**
```bash
webspec-index search "feature name" --limit 5
webspec-index query 'SPEC#section' --format markdown
```

### If crash bug:

Query crash data using `socorro-cli`:
```bash
# Get crash frequency and version breakdown
socorro-cli search --signature "CRASH_SIGNATURE" --days 28

# Get bug associations
socorro-cli bugs --signature "CRASH_SIGNATURE"

# Get a representative stack trace
socorro-cli crash CRASH_ID --depth 15

# Get telemetry-based crash volume (unbiased)
socorro-cli crash-pings --signature "CRASH_SIGNATURE" --days 7 --facet version
```

### If webcompat bug:

Suggest to the engineer that you can hand off to `/webcompat-investigate` for
full reproduction with Firefox/Chrome comparison. If the engineer prefers a
quick check, use the firefox-devtools MCP to:
1. Navigate to the URL
2. Take a screenshot
3. Check console errors

## Phase 2: Analysis

Present the gathered context, then analyze:

1. **Validity**: Is this a real bug? Could this be expected behavior? Is there
   enough information to reproduce? What information is missing?
2. **Spec conformance**: What does the spec say? Is the behavior defined?
   Ambiguous? Is Firefox wrong, or is the other browser wrong?
3. **Code pointers**: Which files and functions are involved? Provide searchfox
   permalinks. Briefly explain what each does.
4. **Related bugs**: Are any of the similar bugs actual duplicates? Has this
   been attempted before? What happened?
5. **For crash bugs**: What is the crash volume? Is it trending up or down?
   Which versions/platforms are affected? Is there an obvious cause from the
   stack trace?

Present the analysis and ask the engineer for their assessment before finalizing.

## Phase 3: Assessment & Output

Based on the analysis, produce the final triage document. Ask the engineer to
confirm the severity recommendation.

### Severity guidelines

- **S1**: Causes data loss, security vulnerability, topcrash, or complete
  feature breakage affecting many users. Needs immediate attention.
- **S2**: Major functionality broken, significant crash volume, or high-traffic
  site broken. Should be fixed soon.
- **S3**: Noticeable issue but with workarounds, moderate crash volume, or
  affects a smaller audience. Should be fixed eventually.
- **S4**: Minor cosmetic issue, very low crash volume, edge case, or the
  affected audience is negligible.

### Difficulty guidelines

- **Small**: Localized change, 1-2 files, clear fix path, low regression risk.
- **Medium**: Multiple files or subsystems involved, requires some domain
  knowledge, moderate regression risk.
- **Large**: Deep engine change, touches many callers, high regression risk,
  may need spec clarification, or requires new infrastructure.

### Output template

Produce this markdown document:

```markdown
## Triage: Bug {id} - {summary}

### Classification
- **Type**: {webcompat | crash | feature-behavior | performance | other}
- **Component**: {product} :: {component}

### Validity
{Is this a real bug? Is it expected behavior? Is info missing?}

### Severity Recommendation: S{n}
{One or two sentences justifying the severity.}

### Spec Situation
{What the spec says. Link to the relevant spec section. Note if ambiguous.}
{If not applicable, say "No spec involvement."}

### Implementation Overview
{Brief description of the relevant code area.}
- [{file}:{function}]({searchfox_permalink}) - {what it does}
- ...

### Size & Difficulty: {small | medium | large}
{One or two sentences explaining why.}

### Where to Start
1. {First step for an engineer picking this up}
2. ...

### Related Bugs
| Bug | Summary | Status | Relevance |
|-----|---------|--------|-----------|
| [{id}](https://bugzilla.mozilla.org/show_bug.cgi?id={id}) | {summary} | {status} | {duplicate / related / prior attempt} |

### Crash Data (if applicable)
- **Signature**: `{signature}`
- **28-day volume**: {n} crashes
- **Affected versions**: {list}
- **Top platforms**: {list}
- **Trend**: {increasing / stable / decreasing}
- **Top frame**: {function name from stack}
```

## Tools reference

### bmo-search
```bash
bmo-search search "terms" [--product P] [--component C] [--status open|closed|all] [--severity S1,S2] [--keywords K] [--crash-signature SIG] [--comments] [--limit N]
bmo-search similar BUG_ID [--limit N]
bmo-search duplicates BUG_ID
bmo-search get BUG_ID [--comments] [--history]
bmo-search advanced -f "field:op:value" [-f ...] [--or] [--limit N]
```

### socorro-cli
```bash
socorro-cli search --signature "SIG" [--days N] [--facet field]
socorro-cli crash CRASH_ID [--depth N] [--all-threads]
socorro-cli crash-pings --signature "SIG" [--days N] [--facet field]
socorro-cli bugs --signature "SIG"
socorro-cli bugs --bug-id BUG_ID
socorro-cli correlations --signature "SIG"
```

### searchfox-cli
```bash
searchfox-cli --define 'Class::Method'
searchfox-cli --define 'Class::Method' --permalink  # get a permalink URL for the output
searchfox-cli --id ClassName [--cpp|--rust|--js] [-l N]
searchfox-cli -q "search term" [--path "glob"] [--only-normal|--only-tests] [-l N]
```

### webspec-index
```bash
webspec-index search "feature" [--spec SPEC] [--limit N]
webspec-index query 'SPEC#anchor' --format markdown
webspec-index exists 'SPEC#anchor'
```
