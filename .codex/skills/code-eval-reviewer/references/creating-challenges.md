# Creating Challenges (Reviewer Reference)

Use this file as the source of truth for hard requirements and checklist items.

## Repository Requirements (Hard)
- Public GitHub repository
- Immutable commit hash (not a branch name or tag)
- At least 1 commit in the last 12 months
- 500+ stars
- Production-level codebase
- Language: TypeScript, JavaScript, Python, Go, or Rust
- Permissive open-source license (see references/allowed-licenses.md)
- Reject if an open or merged PR already fixes the same problem

## Problem Checklist (7)
1. Requirements are complete and self-contained
2. No ambiguities, fully deterministic
3. Problem is concise and not prescriptive
4. Matches real-world repo scope
5. Aligns with repo design philosophy
6. No irrelevant context
7. Clear writing and formatting

## Test Patch Requirements (Hard)
- Valid unified git patch
- Only test changes, no implementation code
- Does not conflict with the solution patch
- No internet required at runtime
- Includes a test.sh script with two modes:
  - ./test.sh base (must pass on base commit)
  - ./test.sh new (must fail on base commit)
- Determinism: no timing-based assertions, no race conditions, no randomness, no network access

## Test Checklist (8)
1. Tests expose unimplemented or incorrect behavior
2. Tests are deterministic
3. Assertions verify correct output
4. Validates behavior, not fragile internals
5. Follows repo test structure
6. Covers required behavior and edge cases
7. No redundant tests
8. No checks for unspecified behavior

## Solution Requirements (Hard)
- Valid unified git patch
- Does not conflict with the test patch
- No new dependencies that require internet at runtime
- Only implementation changes (no Dockerfile modifications)
- With test and solution patches applied: ./test.sh base passes and ./test.sh new passes
- Scope requirement: system-level and multi-file at the challenge level (validated by Shipd agent runs)
- Agent-run requirement: median of successful runs >= 3 files modified and >= 100 agent messages (validated externally)
- Reviewer LOC requirement: solution.patch must add >= 380 non-empty lines (enforced during review; request changes if below 380)
- Reject if solution appears padded with dead code or unnecessary lengthening

## Solution & Code Checklist (6)
1. Meets all requirements
2. No regressions, follows repo patterns
3. No unexplained defensive code
4. No irrelevant changes
5. Existing API contracts stay stable
6. No AI-generated slop, comments, or artifacts

## Dockerfile Requirements (Hard)
- Base image: public.ecr.aws/x8v8d7g8/mars-base:latest
- Install all dependencies during build
- Works with --network none at runtime
- Repository cloned at exact commit hash
- /bin/bash entrypoint
- Works without test.patch or solution.patch applied
- No malicious or suspicious code
