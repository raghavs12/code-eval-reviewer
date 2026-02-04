# Feedback Template

EXACT format for submission feedback. Write naturally, like a tired but thorough senior engineer.

## Required Fields

```
Verdict: [ACCEPT / REJECT / REQUEST_CHANGE]

Problem Quality: [2-4 sentences]

Problem Determinism: [1-3 sentences]

Problem Scope: [1-3 sentences]

Problem Difficulty: [1-2 sentences]

Problem Description <> Test assumptions <> Tests Alignment and Isolation: [2-4 sentences]

Test Quality: [2-3 sentences]

Solution Comprehensiveness: [1-3 sentences]

Code Quality: [1-3 sentences]

Explanation of verdict: [paragraph with specifics]

Ratings:
Problem Quality: [1/2/3]
Problem Determinism: [1/2/3]
Problem Scope: [1/2/3]
Problem Difficulty: [1/2/3]
Test Quality: [1/2/3]
Solution Comprehensiveness: [1/2/3]
Solution Code Quality: [1/2/3]
Quality Score: [1/2/3]
Difficulty Score: [1/2/3]

Ratings and Difficulty Notes:
Test Quality / Score:
3/3: 90-100% perfect, no issues.
2/3: Good, but contains very minor/acceptable mistakes.
1/3: Needs fixes (Do not approve submissions with this rating).
Difficulty:
Most submissions are classified as Medium (2/3). It is your discretion whether a task qualifies as Hard (3/3).
```

---

## Human Writing Rules

1. **Vary your openings** - don't start every field the same way
2. **Use contractions** - "doesn't", "won't", "isn't"
3. **Be specific** - cite line numbers, function names, exact text
4. **Mix sentence lengths** - some short. Others longer when explaining.
5. **Include minor asides** - "(though that's a nitpick)", "not a huge deal but..."
6. **Sound slightly tired/busy** - you're reviewing many of these
7. **Avoid rubric jargon** - do NOT mention R1-R5 or Q1-Q5; plain language only
8. **When requesting changes** - include detailed, actionable feedback
9. **File references** - do not reference files by name; describe content instead
10. **Existing PRs** - mention only if you find a match; don't state "no existing PRs"
11. **Description style** - require behavior-focused statements; call out storytelling intros
12. **Avoid second person** - no "you"; write in neutral, impersonal phrasing
13. **ASCII only** - feedback must contain only ASCII characters
14. **Merged PR case** - still complete all sections with normal content (no "n/a")
15. **Do not stop early** - complete all sections even if one issue is found

---

## Example: ACCEPT

```
Verdict: ACCEPT

Problem Quality: Good real-world problem. Response size limiting for tool calls is something you'd actually want in production MCP servers. The middleware approach fits how fastmcp handles other cross-cutting concerns.

Problem Determinism: No issues here - everything's based on byte counts and string lengths, nothing environment-dependent.

Problem Scope: Well-bounded. Just the middleware + integration with the server, doesn't touch unrelated parts of the codebase.

Problem Difficulty: Feels right for medium. Needs understanding of the middleware pattern and MCP response types, but isn't a rabbit hole.

Problem Description <> Test assumptions <> Tests Alignment and Isolation: Description says what to build, tests verify it without over-constraining. The ToolError requirement for structured responses is mentioned and tested. Only thing - tests assume the middleware class name but that's reasonable since it needs to be importable.

Test Quality: Covers the main cases: under limit, over limit for plain text, over limit for structured (should error). Deterministic. Would've been nice to have a boundary test (exactly at limit) but fine without it.

Solution Comprehensiveness: Handles both response types correctly. The truncation logic for text responses and the ToolError raising for structured ones matches what the description asks for.

Code Quality: Clean implementation, follows the existing middleware patterns in the repo. Nothing fancy but nothing wrong either.

Explanation of verdict: Solid submission overall. The problem is realistic, tests are behavior-focused, and the solution is clean. Accepting as-is.
```

---

## Example: REQUEST_CHANGE

```
Verdict: REQUEST_CHANGE

Problem Quality: The core idea is fine - wheel filename validation is a legit thing. But the description is doing too much.

Problem Determinism: Good - the locale independence test is a nice touch, shows they thought about it.

Problem Scope: Appropriate for the function being modified. Doesn't bleed into unrelated parsing logic.

Problem Difficulty: Medium seems right, maybe on the easier side once you understand the spec.

Problem Description <> Test assumptions <> Tests Alignment and Isolation: This is where it falls apart a bit. Description specifies way more than it needs to. "The validation must occur before tag expansion" - why does a solver need to know this? Just say what should happen, not when internally it should happen. Also the return value section (lines 28-38) just restates what the existing function already returns. The tests also check for exact error substrings which couples them to implementation.

Test Quality: Functionally fine, they cover the cases. But `assert "unsorted compressed tag set" in str(e.value)` on line 9 of test.patch is too specific. Just check it raises InvalidWheelFilename. Same pattern repeats in the other tests.

Solution Comprehensiveness: Does what it needs to do.

Code Quality: Implementation is clean, no complaints there.

Explanation of verdict: The actual problem and solution are fine, but the description needs trimming. Remove lines 5-8 ("Valid, sorted inputs must continue..."), line 12 ("validation must occur before..."), and the entire return values section. That's ~150 words of stuff that's either obvious or over-prescribed. Also change the test assertions to just check exception type, not message content. Once those edits are made this is good to go.
```

---

## Example: REJECT

```
Verdict: REJECT

Problem Quality: Found an existing PR (#847) that implements basically the same thing. The approach is slightly different but it's solving the same problem and it's been open for 3 months with maintainer engagement.

Problem Determinism: Deterministic tests and inputs, no obvious env-specific behavior.

Problem Scope: Scope is limited to the wheel filename parser and related validation logic.

Problem Difficulty: Medium feels right if this were novel.

Problem Description <> Test assumptions <> Tests Alignment and Isolation: Description is clear enough, and tests line up with the described behavior.

Test Quality: Tests look focused on behavior and avoid implementation coupling.

Solution Comprehensiveness: Solution appears to cover the stated cases without obvious gaps.

Code Quality: Implementation reads clean and consistent with repo patterns.

Explanation of verdict: Can't accept this - there's already PR #847 on the repo addressing the same wheel validation gap. Even if this submission's approach is cleaner, we can't have problems that duplicate work that's already in progress on the actual repo. This is a hard reject.
```

---

## Phrases to Use

**Good:**
- "makes sense as a..."
- "fits how the repo handles..."
- "nothing wrong with this"
- "bit verbose but not terrible"
- "the main issue is..."
- "would've liked to see..."
- "not a blocker but..."
- "once you fix X this is good"
- "this is where it falls apart"
- "doesn't need to specify this"
- "just say X, not Y"

**Avoid:**
- "comprehensive"
- "well-structured"
- "demonstrates"
- "This submission..."
- "The problem effectively..."
- "appropriately addresses"
- Starting multiple fields with "The..."

---

## Internal Review Log Template

For documenting steps taken (separate from user-facing feedback):

```
# Submission Review Log

## Overview
Date: [Date]
Reviewer: [Name]
Submission ID: [ID]
Repository: [owner/repo]
Commit: [hash]
Status: [Accepted/Changes Requested/Rejected]

## Stage Results

### Stage 1: Setup
- [Notes]

### Stage 2: Problem Analysis
- Word count: [N]
- Keywords: [list]
- [Issues found]

### Stage 3: Repository
- Stars: [N]
- License: [type]
- Existing PRs: [findings]

### Stage 4: Docker & Base Tests
- Build: [Pass/Fail]
- Base tests: [Pass/Fail]

### Stage 5: New Tests Pre-Solution
- New tests: [X% pass - should be 0%]

### Stage 6: Test Quality
| Aspect | Finding | Severity |
|--------|---------|----------|
| ... | ... | ... |

### Stage 7: AI Judge
- [Agent results and fairness analysis]

### Stage 8: Solution
- Base tests post-solution: [Pass/Fail]
- New tests post-solution: [Pass/Fail]
- [Quality notes]

## Issues Summary
| # | Category | Severity | Description |
|---|----------|----------|-------------|
| 1 | ... | ... | ... |

## Final Verdict
[Decision with reasoning]
```
