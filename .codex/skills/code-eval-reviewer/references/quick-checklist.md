# Quick Review Checklist

Rapid reference for reviews. See `references/rubric-v6.md` and detailed files for full criteria.

---

## 8 Stages

| # | Stage | Key Action |
|---|-------|------------|
| 1 | Setup | Parse files, check duplicates |
| 2 | Problem | Read, count words, check clarity |
| 3 | Repository | Verify stars, license, no existing PR |
| 4 | Docker Base | Build, run `./test.sh base` (PASS) |
| 5 | New Pre-Solution | Run `./test.sh new` (FAIL) |
| 6 | Test Quality | Regressive analysis, alignment check |
| 7 | AI Judge | Analyze agent pass/fail reasons |
| 8 | Solution | Apply, run both tests (PASS/PASS) |

---

## Requirements (R1-R5) Pass/Fail

| R | Check |
|---|-------|
| R1 | ☐ Repo valid, 500+ stars, license OK, no existing PR |
| R2 | ☐ Dockerfile uses mars-base, builds, runs offline |
| R3 | ☐ Problem UTF-8, original, not AI, has issue URL |
| R4 | ☐ Test patch valid, base passes, new fails pre-solution |
| R5 | ☐ Solution patch valid, both tests pass post-solution |

---

## Quality (Q1-Q5) Score 1-3

| Q | Check | Score |
|---|-------|-------|
| Q1 | Problem realistic, 4-8hr difficulty, AI should struggle | ☐ |
| Q2 | Tests deterministic, behavior-focused, follow conventions | ☐ |
| Q3 | ~200 words, no redundancy, WHAT not HOW | ☐ |
| Q4 | Tests cover all stated behaviors, no hidden requirements | ☐ |
| Q5 | Solution clean, idiomatic, minimal, no gaming | ☐ |

---

## Word Count

| Words | Rating |
|-------|--------|
| ~140 | Exemplar |
| ~200 | Acceptable |
| 250+ | Too verbose |

---

## Red Flags → Instant REQUEST_CHANGE

**Problem:**
- [ ] "Don't break existing behavior" (remove)
- [ ] File paths when function name is enough (remove)
- [ ] Implementation timing "before X happens" (remove)
- [ ] Return values that already exist (remove)

**Tests:**
- [ ] `assert "exact string" in str(error)` (just check exception type)

---

## Docker Commands

```bash
# Pre-solution
git apply test.patch
docker build -t shipd/<repo> -f Dockerfile .
docker run -it --network=none shipd/<repo>
./test.sh base  # PASS
./test.sh new   # FAIL

# Post-solution
git apply solution.patch
docker build -t shipd/<repo> -f Dockerfile .
docker run -it --network=none shipd/<repo>
./test.sh base  # PASS
./test.sh new   # PASS
```

---

## Verdict Decision

| Verdict | When |
|---------|------|
| ACCEPT | R1-R5 pass, Q1-Q5 ≥2, ~200 words |
| REQUEST_CHANGE | Fixable issues (give specific edits) |
| REJECT | Existing PR, trivial, nonsense |

---

## Feedback Required Fields

1. Verdict
2. Problem Quality
3. Problem Determinism
4. Problem Scope
5. Problem Difficulty
6. Problem Description <> Test assumptions <> Tests Alignment and Isolation
7. Test Quality
8. Solution Comprehensiveness
9. Code Quality
10. Explanation of verdict

---

## Critical Reminders

- ☐ Complete ALL 8 stages (don't stop early)
- ☐ Regressive analysis: tests FIRST, then check description
- ☐ Search for existing PRs (CRITICAL)
- ☐ If ALL agents fail same reason → investigate unfairness
- ☐ No rubric jargon in feedback (no R1-R5, Q1-Q5)
- ☐ Cite line numbers and specific text
- ☐ ASCII only in feedback
