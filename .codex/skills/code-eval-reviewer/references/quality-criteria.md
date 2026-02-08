# Quality Criteria (Q1-Q5)

## Scoring Scale

| Score | Meaning |
|-------|---------|
| 3 | Fully met, no issues |
| 2 | Partially met, minor gaps |
| 1 | Not met, significant problems |

---

## Q1 - Problem Quality

### Criteria
- **Realistic**: Feels like a real issue/ticket
- **Mergeable**: Feature could actually be merged
- **Challenging**: 4-8+ hours for experienced contributor without AI
- **Verifiable**: Success is objectively measurable
- **Self-contained**: Not a repo-wide refactor

### Scoring

**3: Fully Met**
- Addresses genuine gap or bug in codebase
- Clear real-world use case
- Appropriate scope and difficulty
- State-of-art AI agents should struggle

**2: Partially Met**
- Reasonable but edge case or rarely encountered
- Difficulty slightly off (too easy or too hard)
- Some ambiguity in success criteria

**1: Not Met**
- Made-up or nonsensical feature
- Trivial fix (< 1 hour)
- Success cannot be objectively verified
- Requires repo-wide changes

---

## Q2 - Test Quality

### Criteria
- **Deterministic**: No timing/race/flaky assertions
- **Behavior-focused**: Tests functional correctness, not implementation
- **General**: Any reasonable implementation should pass
- **Follows conventions**: Matches repo testing patterns
- **No exact strings**: Unless part of API contract

### Scoring

**3: Fully Met**
- Tests fully cover behavior including edge cases
- Tests fail at base commit, pass with solution
- Well-integrated into existing test suite
- Names and structure follow repo conventions

**2: Partially Met**
- Minor coverage gaps or missing edge cases
- Partially depends on implementation details
- Mostly follows conventions with minor deviations

**1: Not Met**
- Tests check brittle implementation details
- Flaky or environment-dependent
- Can be passed by hardcoding special cases
- Requires exact error message strings unnecessarily

---

## Q3 - Problem Precision & Conciseness

### Criteria
- **Word count**: <=200 words preferred; <100 is acceptable if complete; >200 needs trimming
- **No redundancy**: Each sentence adds unique value
- **Minimal assumptions**: Only non-obvious interface details
- **No prescriptions**: Describes WHAT not HOW

### Scoring

**3: Fully Met**
- Clearly describes what needs to be done and why
- Professional formatting, no grammar errors
- All requirements concrete and understandable
- Interface definitions ONLY if multiple idiomatic choices exist
- No unnecessary information

**2: Partially Met**
- Task adequate but minor details ambiguous/incomplete
- Minor grammar errors or formatting issues
- Some unnecessary information that should be inferable

**1: Not Met**
- Task significantly unclear or incomplete
- Important interface specs or context missing
- Severe grammar errors affecting comprehension
- Overly verbose with redundant content

### What to Include vs Exclude

**Include (Test Assumptions):**
- New function/class names when not obvious
- New file paths when multiple reasonable choices exist
- Specific error types/codes if tested
- CLI flags or API parameters if non-obvious

**Exclude:**
- Implementation algorithms
- Obvious naming (parse_toml when parse_json exists)
- Things inferable from existing code patterns
- "Don't break existing functionality"
- Background stories not affecting requirements

---

## Q4 - Problem/Test Alignment & Isolation

### Criteria
- **Coverage**: Tests cover all stated behaviors
- **No hidden requirements**: Tests don't enforce unstated behaviors
- **Isolation**: Problem description doesn't mention specific tests
- **Edge cases**: Reasonable effort to cover boundaries

### Scoring

**3: Fully Met**
- All requirements from description are tested
- No surprises in tests (nothing unstated)
- Test Assumptions lists only what tests rely on
- Problem doesn't reference test implementation

**2: Partially Met**
- Some minor requirements lack test coverage
- Minor hidden requirements in tests
- Could lead to different valid implementations

**1: Not Met**
- Major requirements untested
- Tests enforce significant unstated behaviors
- Tests can be gamed without solving real problem
- Problem explicitly describes test structure

---

## Q5 - Solution Quality

### Criteria
- **Legitimate**: Solves the actual problem
- **No gaming**: Doesn't exploit test weaknesses
- **Clean**: Idiomatic, maintainable code
- **Minimal**: No unnecessary changes
- **Safe**: No security/performance red flags

### Scoring

**3: Fully Met**
- Clean, idiomatic implementation
- Follows repo patterns and conventions
- Minimal changes to solve problem
- No dead code or magic values

**2: Partially Met**
- Works but could be cleaner
- Minor style deviations
- Slightly more changes than necessary

**1: Not Met**
- Hacky solution to satisfy tests
- Test gaming (special-casing test inputs)
- Unnecessary complexity or refactoring
- Security/performance concerns
- Changes unrelated files

---

## Regressive Analysis Quality Check

For each test, verify:

1. **Requirement Extraction**
   - Can you write "Given X, when Y, should Z"?
   - Is the requirement stated in description?

2. **Determinism**
   - Same input → same output always?
   - No OS/locale/timezone dependencies?

3. **Offline Solvability**
   - If external spec needed, is it included?
   - Can solver complete without internet?

4. **Interface Stability**
   - What must remain unchanged?
   - Are return types/exceptions stable?
