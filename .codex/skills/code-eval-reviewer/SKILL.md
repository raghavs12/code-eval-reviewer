---
name: code-eval-reviewer
description: Review Project Mars/Datacurve problem submissions using only the problems folder as source of truth, run Docker verification for patches without waiting for user prompting, and produce feedback only (no edits) in feedback.md inside the problem folder. Use for "review problem", "evaluate submission", or Mars assessment files.
---

# Code Eval Reviewer

## Workflow

1. **Locate the problem folder** under `problems/` and treat it as the only source of truth
2. **Read problem files** from that folder (description.md, dockerfile, test.patch, solution.patch)
3. **Check requirements** - see `references/requirements-checklist.md` if unsure
4. **Regressive analysis**: Read tests FIRST -> extract what they enforce -> check if description matches
5. **Score quality** - see `references/quality-criteria.md` for scoring
6. **Run Docker verification** for patches (always do this without user prompting)
7. **Generate feedback** - see `references/feedback-template.md` for exact format
8. **Write output** to `feedback.md` inside the same problem folder
9. **Write review steps** to `step.md` inside the same problem folder (include every step taken)
10. **Watch for anti-patterns** - see `references/common-issues.md`

## Quick Benchmarks

| Rating | Words | Technical Requirements |
|--------|-------|----------------------|
| Exemplar | ~140 | Empty or minimal |
| Acceptable | ~200 | Only non-obvious items |
| Too verbose | 250+ | Needs trimming |

## Verdict Decision

- **ACCEPT**: Requirements pass + quality good + ~200 words
- **REQUEST_CHANGE**: Fixable issues (give specific edits)
- **REJECT**: Existing PR, nonsense feature, trivial solution (use sparingly)

## Docker Verification

```bash
# Clone repo, checkout commit, copy dockerfile
docker build -t test .
docker run --network=none test ./test.sh base  # must pass
docker run --network=none test ./test.sh new   # must fail without solution

# Apply both patches
docker run --network=none test ./test.sh base  # must pass
docker run --network=none test ./test.sh new   # must pass
```

Do not edit any problem files or other code while running Docker verification.

## Red Flags (instant REQUEST_CHANGE)

**Description:**
- "Don't break existing behavior" -> remove (obvious)
- File paths when function name is enough -> remove
- Implementation timing ("before X happens") -> remove
- Return values that already exist -> remove

**Tests:**
- `assert "exact string" in str(error)` -> just check exception type

## Output Format

```
Verdict: [ACCEPT/REJECT/REQUEST_CHANGE]
Problem Quality: [2-4 sentences]
Problem Determinism: [1-3 sentences]
Problem Scope: [1-3 sentences]
Problem Difficulty: [1-2 sentences]
Problem Description <> Test assumptions <> Tests Alignment and Isolation: [2-4 sentences]
Test Quality: [2-3 sentences]
Solution Comprehensiveness: [1-3 sentences]
Code Quality: [1-3 sentences]
Explanation of verdict: [specific issues + required edits]
```

Write like a tired senior engineer - use contractions, vary sentences, be direct, cite line numbers.
Never edit problem files or any other code. Always create `feedback.md` inside the problem folder (it may not exist) and write feedback there only. Also create `step.md` inside the problem folder with a complete, step-by-step account of how the problem was reviewed.
