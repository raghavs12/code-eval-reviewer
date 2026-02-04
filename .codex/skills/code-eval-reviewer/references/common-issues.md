# Common Issues & Anti-Patterns

## Word Count Benchmarks

| Rating | Words | Assessment |
|--------|-------|------------|
| Exemplar | ~140 | Minimal, behavior-focused |
| Acceptable | ~200 | Good balance |
| Too verbose | 250+ | Needs trimming |

**Target: ~200 words. Above 250 needs strong justification.**

---

## Problem Description Issues

### Over-Specification (Too Prescriptive)

**Bad:**
```markdown
## Agent Instructions
1. Fix Fraction Serialization
   Match Decimal behavior:
   - `model_dump()` --> `Fraction` objects
   - `model_dump_json()` --> strings (e.g., `"1/3"`)
   - Zero fractions serialize as `"0"` instead of `"0/1"`
```

**Better:**
```markdown
## Agent Instructions
Fraction should serialize consistently with Decimal: objects in Python mode,
strings in JSON mode. Fraction(4, 6) should become '2/3' when serialized.
```

**Why:** A competent developer should figure everything else out.

---

### Redundant/Obvious Information

These EXACT phrases should be flagged and removed:

| Phrase | Why Remove |
|--------|------------|
| "Valid, sorted inputs must continue to parse exactly as before" | Obvious - don't break existing behavior |
| "Behavior must be deterministic and independent of environment" | Implied for any fix |
| "The validation must occur before tag expansion" | Specifies internal implementation timing |
| "Do not change how tags are generated; only add validation" | Creates confusion by suggesting extra changes |
| "Preserve existing public types and exceptions" | Obvious from context |
| "Maintain backward compatibility" | Always expected unless stated otherwise |

---

### Specifying Location When Obvious

**Bad:**
```markdown
## Technical Requirements
Location: src/packaging/utils.py
Public function parse_wheel_filename:
```

**Better:** Just say "the wheel filename parser" - devs can find it.

---

### Specifying Return Values That Already Exist

**Bad:**
```markdown
Return values:
Project name: canonicalized string as currently produced.
Version: an instance of packaging.version.Version.
Build: when present, a tuple[int, str]...
```

**Fix:** Delete entire section - restates what function already returns.

---

### Implementation Leakage

**Bad:**
```
Fix a bug in shipd_reviewer where it throws an error by correcting 
the logic of parsing to use string parser instead of integer parser.
```

**Good:**
```
Fix the issue in shipd_reviewer function as it's throwing error on passing username.
```

**Why:** The solver (AI) should determine HOW to implement.

---

## Test Issues

### Implementation-Coupled Tests

**Bad - checking exact error substring:**
```python
def test_error_message():
    with pytest.raises(InvalidWheelFilename) as e:
        parse_wheel_filename(bad_input)
    assert "unsorted compressed tag set" in str(e.value)  # ❌
```

**Better:**
```python
def test_rejects_invalid_input():
    with pytest.raises(InvalidWheelFilename):
        parse_wheel_filename(bad_input)
    # Just check exception type, not exact message
```

**Why:** Exact string requirements constrain implementation unnecessarily.

---

### Tests That Can Be Gamed

**Bad:**
```python
def test_handles_special_case():
    assert process("test_input_1") == "expected_1"
    assert process("test_input_2") == "expected_2"
    # Only two specific inputs tested
```

**Why:** Can be passed by: `if input == "test_input_1": return "expected_1"`

**Better:** Test general behavior with varied inputs, edge cases.

---

### Missing Edge Cases

**Problem says:** "Handle negative numbers and zero"

**Tests only check:**
```python
def test_positive():
    assert func(5) == 25
```

**Missing:** Tests for -5, 0, boundary values

---

### Flaky/Non-Deterministic Tests

**Bad:**
```python
def test_timing():
    start = time.time()
    result = slow_operation()
    assert time.time() - start < 1.0  # Flaky on slow machines

def test_random():
    result = generate_random_id()
    assert len(result) == 10  # May fail if randomness changes
```

---

### Weak Assertions

**Problem:** `expectErr` helpers that only check if error occurred, not content.

```go
expectErr := func(t *testing.T, kind string, err error) {
    if err == nil {
        t.Fatalf("expected error for %s, got ok", kind)
    }
}
```

**Severity:** Minor if matches repo pattern, Critical if repo uses specific assertions.

---

### Hidden Requirements

Tests that validate behavior NOT mentioned in problem description.

**Detection:** Compare test assertions against explicit requirements. Any test without corresponding requirement is a surprise test.

**Fix:** Either add requirement to problem OR remove test.

---

### AI Traces in Tests

If test file has comments but similar repo files don't use comments = AI indicator.

Check for:
- Style inconsistencies with existing tests
- Generic variable names
- Over-documented obvious code

---

## Solution Issues

### Test Gaming

**Problem:** Parse and validate input format

**Bad Solution:**
```python
def validate(input):
    if input == "test_case_1":
        return True
    if input == "test_case_2":
        return False
    # actual logic missing
```

---

### Unnecessary Complexity

**Problem:** Add a simple validation

**Bad Solution:**
```python
class ValidationStrategy(ABC):
    @abstractmethod
    def validate(self, input): pass

class StringValidator(ValidationStrategy):
    # ... 100 lines of over-engineering
```

**Better:** Simple function that does the job.

---

### Magic Values

**Bad:**
```python
def process(data):
    if len(data) > 1337:  # Why this number?
        raise ValueError("Too large")
```

**Better:** Use named constants with clear meaning.

---

### Dead Code After Changes

If solution adds new methods that replace old ones, old methods should be removed if now unused.

---

### Hardcoded Values

**Bad:**
```go
if userCount > 100 {
    return "large"
}
```

**Good:**
```go
if userCount > threshold {
    return "large"
}
```

---

## AI Judge Analysis

### When All Agents Fail for Same Reason

**Critical warning sign** of potential unfairness:
- Vague problem description
- Hidden requirements in tests
- Tricky wording / non-determinism
- Inconsistent casing (X-Death vs x-death)

**Action:** Investigate root cause before accepting/rejecting.

### Don't Trust Tags Blindly

Tags like GOOD/BAD or FAIL_UNDOCUMENTED_REQUIREMENT may be inaccurate.

**Always verify:**
- Read the actual failure reason
- Check if failure is due to legitimate difficulty vs unfairness
- Confirm "undocumented requirement" is actually undocumented

### Fair vs Unfair Failures

| Fair Failure | Unfair Failure |
|--------------|----------------|
| Agent misunderstood clearly stated requirement | Requirement not stated or inferable |
| Agent made implementation error | Tricky casing/naming not specified |
| Problem is legitimately complex | Hidden test requirements |
| Agent used wrong approach | Ambiguous wording with multiple interpretations |

---

## Verdict Decision Guide

### REJECT If:
- Existing PR on GitHub solving same issue
- Made-up nonsensical feature
- Solution is trivial (< 2 lines)
- Tests can be passed without solving problem

### REQUEST CHANGE If:
- Description too verbose (can be trimmed)
- Missing test coverage for stated requirements
- Over-specified technical details
- Minor alignment issues
- Fixable code quality issues

### ACCEPT If:
- All R1-R5 requirements pass
- Q1-Q5 scores are 2 or higher
- No major issues in regressive analysis
- Word count reasonable (~200)

---

## Feedback Writing Tips

### Be Specific
**Bad:** "Description is too verbose"
**Good:** "Remove paragraph 2 lines 5-8, this information is inferable from existing code patterns"

### Be Actionable
**Bad:** "Tests need improvement"
**Good:** "Add test case for empty input: `assert func('') raises ValueError`"

### Quote Problems
**Bad:** "Error message check is too strict"
**Good:** "Line 45: `assert 'unsorted' in str(e)` - remove this assertion, just check exception type"

### Prioritize
1. Blockers (must fix)
2. Should fix (quality improvement)
3. Nice to have (minor polish)
