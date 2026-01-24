---
name: code-eval-reviewer
description: Review code problem submissions (description.md, dockerfile, test.patch, solution.patch) for Project Mars/Datacurve assessments. Runs Docker verification, applies regressive analysis (tests→requirements→description), generates human-sounding feedback. Use for "review problem", "evaluate submission", or Mars assessment files.
---

# Code Eval Reviewer

## Workflow

1. **Read problem files** (description.md, dockerfile, test.patch, solution.patch)
2. **Check requirements** - see `references/requirements-checklist.md` if unsure
3. **Regressive analysis**: Read tests FIRST → extract what they enforce → check if description matches
4. **Score quality** - see `references/quality-criteria.md` for scoring
5. **Generate feedback** - see `references/feedback-template.md` for exact format
6. **Watch for anti-patterns** - see `references/common-issues.md`

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

## Red Flags (instant REQUEST_CHANGE)

**Description:**
- "Don't break existing behavior" → remove (obvious)
- File paths when function name is enough → remove
- Implementation timing ("before X happens") → remove
- Return values that already exist → remove

**Tests:**
- `assert "exact string" in str(error)` → just check exception type

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
