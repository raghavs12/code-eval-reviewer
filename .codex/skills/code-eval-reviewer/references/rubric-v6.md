# Project Mars Evaluation Rubric v6

## Data Format

- **Environment**: GitHub repo URL + commit hash
- **Dockerfile**: `problem/dockerfile`
- **Problem**: problem description (task brief, developer instructions, test assumptions). Sections may be named differently or omitted.
- **Test patch**: `problem/test.patch`
- **Solution patch**: `problem/solution.patch`

All problem info is inside `problem/`. Do not assume or read from any other folder.

## R - Requirements (review order)

### R1 GitHub Repository

- URL + commit hash valid
- Active: at least 1 commit in last 12 months
- Reputable, production-level, at least 500 stars
- Main language: TypeScript, JavaScript, or Python
- Open-source, permissive license (see Allowed Licenses below)
- GitHub issue URL is provided if available
- Check for existing GitHub issue or PR solving the same problem
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
- GitHub Issue URL provided if available
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
| Exemplar | ~140 | Empty or minimal |
| Acceptable | ~200 | Only non-obvious items |
| Too verbose | 250+ | Needs trimming |

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

## Allowed Licenses

- MIT License (MIT)
- BSD-1-Clause
- BSD 2-Clause "Simplified" License (BSD-2-Clause)
- BSD-2-Clause-Flex
- BSD 2-Clause FreeBSD License (BSD-2-Clause-FreeBSD)
- BSD-2-Clause-Modification
- BSD-2-Clause Plus Patent License (BSD-2-Clause-Patent)
- BSD 2-Clause with views sentence (BSD-2-Clause-Views)
- BSD 3-Clause "New" or "Revised" License (BSD-3-Clause)
- BSD with attribution (BSD-3-Clause-Attribution)
- BSD-3-Clause-EricHeitz
- BSD-3-Clause-HealthLevelSeven
- Lawrence Berkeley National Labs BSD variant license (BSD-3-Clause-LBNL)
- BSD-3-Clause-Modification
- BSD-3-Clause-OpenMPI
- BSD-3-Clause-plus-CMU-Attribution
- BSD-3-Clause-plus-Paul-Mackerras-Attribution
- BSD-3-Clause-plus-Tommi-Komulainen-Attribution
- BSD 4-Clause "Original" or "Old" License (BSD-4-Clause)
- BSD-4-Clause-Argonne
- BSD-4-Clause-Atmel
- BSD-4-Clause-Giffin
- BSD 4-Clause PC/SC Lite for Suse (BSD-4-Clause-PC-SC-Lite)
- BSD-4-Clause-Plus-Modification-Notice
- BSD-4-Clause (University of California-Specific) (BSD-4-Clause-UC)
- BSD-4-Clause-Visigoth
- BSD-4-Clause-Vocal
- BSD-4-Clause (Wasabi-Specific) (BSD-4-Clause-Wasabi)
- BSD 4.3 TAHOE License (BSD-4.3TAHOE)
- BSD-5-Clause
- BSD-FatFs
- BSD-Mixed-2-Clause-And-3-Clause
- BSD Protection License (BSD-Protection)
- BSD Source Code Attribution (BSD-Source-Code)
- Boost Software License 1.0 (BSL-1.0)
- BLAS
- GNU-All-permissive-Copying-License
- Apache License 2.0 (Apache-2.0)
- Apache-2.0-Modified
- Apache-with-LLVM-Exception
- Apache-with-Runtime-Exception
- BSD-2-Clause Plus Patent License (BSD-2-Clause-Patent)
- Creative Commons Attribution 1.0 Generic (CC-BY-1.0)
- Creative Commons Attribution 2.0 Generic (CC-BY-2.0)
- Creative Commons Attribution 2.5 Generic (CC-BY-2.5)
- Creative Commons Attribution 3.0 Unported (CC-BY-3.0)
- Creative Commons Attribution 4.0 International (CC-BY-4.0)
