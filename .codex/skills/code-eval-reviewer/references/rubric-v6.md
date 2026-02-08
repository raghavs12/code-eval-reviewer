# Project Mars Evaluation Rubric v6

## Data Format

- **Quick-Setup.txt**: Repo URL, commit hash, test patch, Dockerfile, test.sh
- **Problem-Description.txt**: Task brief, requirements, test assumptions
- **Solution.txt**: Solution patch (git diff format)

All problem info is inside these files. Do not assume or read from any other folder.

## R - Requirements (review order)

### R1 GitHub Repository (Do this first. If it fails, reject immediately and still write feedback.md)

Checking for existing PRs or issues that already solve the same problem is critical and must be done every time.

- URL + commit hash valid
- Active: at least 1 commit in last 12 months
- Reputable, production-level, at least 500 stars
- Main language: TypeScript, JavaScript, Python, Go, or Rust
- Open-source, permissive license (see `references/allowed-licenses.md`)
- GitHub issue URL is optional; it does not need to be mentioned in the description if it already exists
- Check for existing GitHub issue or PR solving the same problem:
  - Pull the repo + issue info from Quick-Setup.txt
  - Search GitHub PRs (open + merged) for keywords in title/body
  - Search issues + PRs together with broader keywords
  - Open the provided issue and check if it is closed/resolved; if closed, reject immediately. Also check for linked PRs or references
  - Skim results for anything that looks like the same feature (title/body overlap)
  - If you find a likely match, open that PR to confirm scope
  - If there is an open PR or merged PR that fixes the same issue/problem, reject immediately
- Contact Shipd team if license or reputability is unclear

### R2 Dockerfile

- Base image: `public.ecr.aws/x8v8d7g8/mars-base:latest`
- Installs dependencies for building and testing
- After image build, tests can run offline
- Works without test.patch and solution.patch applied
- Uses `/bin/bash` entrypoint
- No malicious or suspicious code

### R3 Problem

- UTF-8 text
- Not AI generated, not malicious, not plagiarized
- GitHub Issue URL is optional; not required to be mentioned in the description
- Must not describe problems already fixed (closed issue, existing PR, etc)

### R4 Test

- Test patch is a valid git patch
- Does not conflict with solution patch and can be applied in any order
- Only test changes (no solution or dockerfile changes)
- Includes `test.sh`:
  - `./test.sh base` runs existing tests, must pass, excludes flaky or broken tests
  - `./test.sh new` runs new or modified tests, must fail without solution patch
- No internet required
- No malicious code

### R5 Solution

- Solution patch is a valid git patch
- Does not conflict with test patch and can be applied in any order
- No new deps requiring internet
- Only solution implementation (no dockerfile changes)
- Can include test changes only if old test was broken and relevant
- With solution + test patch applied:
  - `./test.sh base` passes (no regression)
  - `./test.sh new` passes
- No malicious code

## Q - Quality (review order)

### Q1 Problem Quality

- Realistic, like a real issue or ticket
- Clear what to build or fix (why is optional)
- Feature requests are realistic and mergeable
- Appropriately challenging, not trivial or repo-wide refactor
- Success is objectively verifiable
- Target effort: medium-hard (4-8+ hours for experienced contributor)
- Current AI agents should struggle

### Q2 Test Quality

- Deterministic, no timing or flaky assertions
- Behavior-focused, not implementation details
- Follows repo conventions
- Avoid exact strings unless part of API or business contract
- Minimal explicit assumptions only when unavoidable

### Q3 Problem Precision and Conciseness

- Clear without being verbose
- Test Assumptions list only non-obvious interface details
- Avoid prescribing algorithms, structure, or exact messages unless required
- Remove obvious statements (for example, "don't break existing behavior")

### Q4 Problem and Test Alignment and Isolation

- Tests cover all behaviors stated in the problem
- Reasonable edge case coverage
- No hidden requirements in tests
- Test Assumptions list only what tests must rely on
- Problem description does not mention new tests

### Q5 Solution Quality

- Legit implementation of described problem
- No test gaming
- Clean, idiomatic, maintainable, follows repo patterns
- No unnecessary complexity or magic values
- No security or performance red flags

## Quick Benchmarks

| Rating | Words | Technical Requirements |
|--------|-------|----------------------|
| Exemplar | <100 | Minimal, behavior-focused, no hidden assumptions |
| Acceptable | 100-200 | Only non-obvious items |
| Too verbose | >200 | Needs trimming |

## Verdict Decision

- **ACCEPT**: Requirements pass + quality good + ~200 words
- **REQUEST_CHANGE**: Fixable issues (give specific edits)
- **REJECT**: Existing PR, nonsense feature, trivial solution (use sparingly)

## Red Flags (instant REQUEST_CHANGE)

**Description:**
- "Don't break existing behavior" -> remove (obvious)
- File paths when function name is enough -> remove
- Implementation timing ("before X happens") -> remove
- Return values that already exist -> remove

**Tests:**
- `assert "exact string" in str(error)` -> just check exception type
