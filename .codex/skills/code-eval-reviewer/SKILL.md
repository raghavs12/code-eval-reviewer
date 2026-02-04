---
name: code-eval-reviewer
description: Review Shipd MARS project submissions using the problem inputs as source of truth, run Docker verification without prompting, and write structured feedback to feedback.md in the repo root. Follow the 8-stage workflow with R1-R5 requirements and Q1-Q5 quality scoring. Triggers on "review submission", "Shipd review", "MARS review", or when Quick-Setup.txt/Problem-Description.txt/Solution.txt files are provided.
---

# Shipd MARS Reviewer

## Workflow Overview

1. **Parse input files** - Quick-Setup.txt, Problem-Description.txt, Solution.txt
2. **Follow 8-stage review** - Complete ALL stages regardless of issues found
3. **Use regressive analysis** - Read tests FIRST -> extract requirements -> check if description matches
4. **Run Docker verification** - Execute exact commands without user prompting
5. **Score R1-R5 requirements** - Pass/Fail for each requirement
6. **Score Q1-Q5 quality** - 1-3 scale for each quality dimension
7. **Use rubric-v6 as source of truth** - See `references/rubric-v6.md` for evaluation details and verdicts
8. **Calibrate with examples if unsure** - See `references/examples/` (example-1-uploaded)
9. **Generate feedback** - Use exact template format and write to `feedback.md` in the repo root. Create `feedback.md` if it is not there.
10. **Write review log** - Write `review_log.md` in the repo root using `references/examples/example-1-uploaded/Submission Review Log.md` as the template.
11. **Document steps** - Record every action taken during review

## Input Files

| File | Contents |
|------|----------|
| Quick-Setup.txt | Repo URL, commit hash, test patch, Dockerfile, test.sh |
| Problem-Description.txt | Task brief, requirements, test assumptions |
| Solution.txt | Solution patch (git diff format) |

---

## 8-Stage Review Process

### Stage 1: Setup & Initial Checks

**Actions:**
1. Parse Quick-Setup.txt to extract repo URL, commit, patches
2. Check for duplicate submissions (similarity scores)
3. Check for multiple solutions (prioritize author's)

**Document:** Setup status, duplicate check results

---

### Stage 2: Problem Description Analysis

**Actions:**
1. Read problem thoroughly, identify keywords
2. Count words (target ~200, max 250)
3. Check for over-specification and redundancy
4. Determine if self-created or based on GitHub issue

**Red Flags to Remove:**
- "Don't break existing behavior" (obvious)
- File paths when function name is enough
- Implementation timing ("before X happens")
- Return values that already exist in code
- Algorithm prescriptions

**Document:** Problem type, word count, clarity issues

---

### Stage 3: Repository Verification (R1)

**Checklist:**
- [ ] GitHub URL + commit valid
- [ ] Active: ≥1 commit in last 12 months
- [ ] Reputable: ≥500 stars
- [ ] Language: TypeScript, JavaScript, or Python
- [ ] License: Permissive (see `references/allowed-licenses.md`)
- [ ] No existing PR/issue solving same problem

**Critical:** Search GitHub PRs (open + merged) and issues for keywords. Open provided issue and check for linked PRs.

---

### Stage 4: Docker Build & Base Tests (R2, R4 partial)

**Exact Commands:**
```bash
git apply "test.patch"
docker build -t shipd/<repo-name> -f "Dockerfile" .
docker run -it --network=none shipd/<repo-name>
# inside container:
sed -i 's/\r$//' ./test.sh
./test.sh base  # MUST PASS
./test.sh new   # MUST FAIL
```

**Dockerfile Requirements:**
- Base image: `public.ecr.aws/x8v8d7g8/mars-base:latest`
- Entrypoint: `/bin/bash`
- Tests run offline after build
- No malicious code

---

### Stage 5: New Tests Pre-Solution (R4)

**Expected:** `./test.sh new` = 0% pass (all failing)

**Why:** Confirms tests actually test NEW functionality. Tests passing without solution = weak/redundant.

**Flag:** Any test passing unexpectedly needs review.

---

### Stage 6: Test Quality Inspection (Q2, Q4)

**Regressive Analysis - For each test:**
1. Write "Given X, when Y, should Z"
2. Is this requirement in description?
3. Same input → same output always?
4. Can solver complete without internet?

**Quality Checklist:**
| Aspect | Check |
|--------|-------|
| Determinism | No timing, race, flaky assertions |
| Behavior-focused | Tests outcome, not implementation |
| General | Any reasonable implementation should pass |
| Conventions | Matches repo testing patterns |
| No exact strings | Unless API contract |
| No hidden requirements | Tests only stated behaviors |

**Document findings in table format.**

---

### Stage 7: AI Judge Analysis

**Actions:**
1. Review holistic_ai_judge results
2. Review problem_ai_difficulty results
3. Analyze WHY agents passed/failed

**Critical:** If ALL agents fail for SAME reason → investigate unfairness:
- Vague problem description
- Hidden requirements in tests
- Tricky wording / non-determinism

**Don't trust tags blindly** - GOOD/BAD may be inaccurate.

---

### Stage 8: Solution Review (R5, Q5)

**Apply Solution:**
```bash
git apply "solution.patch"
docker build -t shipd/<repo-name> -f "Dockerfile" .
docker run -it --network=none shipd/<repo-name>
./test.sh base  # MUST PASS
./test.sh new   # MUST PASS
```

**Solution Checklist:**
- [ ] Legitimate implementation (not test gaming)
- [ ] Clean, idiomatic, follows repo patterns
- [ ] Minimal changes to solve problem
- [ ] No dead code or magic values
- [ ] No security/performance red flags
- [ ] Does ONLY what's asked
- [ ] Does ALL that's asked

---

## Scoring

### Requirements (R1-R5): Pass/Fail

| Req | Description |
|-----|-------------|
| R1 | GitHub repo valid, active, reputable, no existing fix |
| R2 | Dockerfile correct base image, offline tests, bash entrypoint |
| R3 | Problem UTF-8, original, not AI, issue URL if available |
| R4 | Test patch valid, test.sh has base/new, new fails without solution |
| R5 | Solution patch valid, both tests pass with solution |

### Quality (Q1-Q5): Score 1-3

| Score | Meaning |
|-------|---------|
| 3 | Fully met, no issues |
| 2 | Partially met, minor gaps |
| 1 | Not met, significant problems |

See `references/rubric-v6.md` and `references/quality-criteria.md` for detailed scoring guide.

---

## Word Count Benchmarks

| Rating | Words | Assessment |
|--------|-------|------------|
| Exemplar | ~140 | Minimal, behavior-focused |
| Acceptable | ~200 | Good balance |
| Too verbose | 250+ | Needs trimming |

---

## Verdict Decision

| Verdict | When |
|---------|------|
| **ACCEPT** | R1-R5 pass + Q1-Q5 ≥2 + ~200 words |
| **REQUEST_CHANGE** | Fixable issues (give specific edits) |
| **REJECT** | Existing PR, nonsense feature, trivial solution |

---

## Feedback Format

See `references/feedback-template.md` for exact format.

**Writing Rules:**
1. Vary openings - don't start every field same way
2. Use contractions - "doesn't", "won't", "isn't"
3. Be specific - cite line numbers, function names
4. Mix sentence lengths
5. Sound slightly tired/busy
6. Avoid rubric jargon (no R1-R5, Q1-Q5 in output)
7. No "you" - neutral, impersonal phrasing
8. ASCII only
9. Don't stop early - complete all sections even if issue found

---

## Key Principles

1. **Complete ALL stages** - Don't stop early except mandatory rejection
2. **Regressive analysis** - Tests FIRST, then check description alignment
3. **One-shot feedback** - Identify every flaw in single pass
4. **Verify claims** - Prove issues with evidence, line numbers
5. **Specific fixes** - Include exact edits required
6. **Prioritize fairness** - Hidden requirements = unfair

## References

- `references/quality-criteria.md` - Q1-Q5 scoring details
- `references/rubric-v6.md` - R1-R5/Q1-Q5 rubric and verdict rules
- `references/requirements-checklist.md` - R1-R5 validation
- `references/common-issues.md` - Anti-patterns with examples
- `references/examples/` - Calibration example and review log template (example-1-uploaded)
- `references/feedback-template.md` - Exact output format
- `references/allowed-licenses.md` - Permissive license list
- `references/docker-commands.md` - Exact verification commands
