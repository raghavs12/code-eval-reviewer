# Common Issues & Anti-Patterns

Based on actual example submissions - use these exact patterns to judge quality.

## Word Count Benchmarks

| Rating | Words | Example |
|--------|-------|---------|
| Exemplar | ~140 | FastAPI response headers |
| Good | ~200-240 | Pydantic fraction (but too prescriptive) |
| Needs Improvement | 500+ | Wheel filename parser |

**Target: ~200 words. Above 250 needs strong justification.**

## Problem Description Issues

### Over-Specification (Too Prescriptive)

**Bad Example (from Example 2 - "Good"):**
```markdown
## Agent Instructions
1. Fix Fraction Serialization
   Match Decimal behavior:
   - `model_dump()` --> `Fraction` objects
   - `model_dump_json()` --> strings (e.g., `"1/3"`)
   - Zero fractions serialize as `"0"` instead of `"0/1"`
   - Support parsing string inputs like `"1/3"`, `"-1/2"`
```

**Better (reviewer feedback):**
```markdown
## Agent Instructions
Fraction should serialize consistently with Decimal: objects in Python mode,
strings in JSON mode. Fraction(4, 6) should become '2/3' when serialized as string.
```

**Why:** "A competent developer should be able to figure everything else out"

---

### Redundant/Obvious Information (from Example 3 - "Needs Improvement")

These EXACT phrases should be flagged and removed:

**❌ "Valid, sorted inputs must continue to parse exactly as before"**
- Reviewer: "This is unnecessary" - it's obvious you shouldn't break existing behavior

**❌ "Behavior must be deterministic and independent of environment"**  
- Implied for any fix, doesn't need stating

**❌ "The validation must occur before tag expansion and must not alter parsing for already valid inputs"**
- Reviewer: "This is repetitive" - specifies internal implementation timing

**❌ "Do not change how tags are generated or canonicalized; only add the required validation"**
- Reviewer: "This is unnecessary. Creates confusion by suggesting extra changes that aren't required"

**❌ "Preserve existing public types and exceptions"**
- Obvious from context

---

### Specifying Location When Obvious (from Example 3)

**Bad:**
```markdown
## Technical Requirements
Location: src/packaging/utils.py
Public function parse_wheel_filename:
```

**Reviewer feedback:** "This is too detailed. Based on the codebase context, this function should be locatable just given 'The wheel filename parser'"

**Better:** Just say "the wheel filename parser" - devs can find it

---

### Specifying Return Values That Already Exist (from Example 3)

**Bad:**
```markdown
Return values:
Project name: canonicalized string as currently produced by the module.
Version: an instance of packaging.version.Version parsed from the version field.
Build: when present, a tuple[int, str]...
Tags: a frozenset[Tag] representing all expanded tags...
```

**Reviewer feedback:** "Developers should be able to already determine this from the existing code, since this part is not changing"

**Fix:** Delete entire section - it's restating what the function already returns

---

## Test Issues

### Implementation-Coupled Tests (from Example 3)

**Bad - checking exact error substring:**
```python
def test_error_message():
    with pytest.raises(InvalidWheelFilename) as e:
        parse_wheel_filename(bad_input)
    assert "unsorted compressed tag set" in str(e.value)  # ❌ Exact string!
```

**Reviewer feedback:** "I would rather have the tests not check for a given substring. There can be enough test cases to ensure the function is treating all valid and invalid inputs correctly without specifically checking for this."

**Better:**
```python
def test_rejects_invalid_input():
    with pytest.raises(InvalidWheelFilename):
        parse_wheel_filename(bad_input)
    # Just check exception type, not exact message
```

**Why:** Exact string requirements constrain implementation unnecessarily.

---

### Good Test Example (from Example 1 - Exemplar)

```python
def test_response_headers_validation_error():
    """Test that invalid response headers raise validation errors"""
    app = FastAPI()

    @app.get("/items", response_headers=ResponseHeaders)
    def get_items():
        response = JSONResponse(content={"items": ["item1"]})
        response.headers["X-Rate-Limit"] = "-5"  # Invalid: should be >= 0
        return response

    client = TestClient(app)
    with pytest.raises(ResponseValidationError):
        client.get("/items")
```

**Why this is good:**
- Tests behavior (invalid header raises error)
- Doesn't check exact error message
- Clear setup and assertion
- Follows repo conventions

---

### Tests That Can Be Gamed

**Bad:**
```python
def test_handles_special_case():
    assert process("test_input_1") == "expected_1"
    assert process("test_input_2") == "expected_2"
    # Only two specific inputs tested
```

**Why:** Can be passed by hardcoding: `if input == "test_input_1": return "expected_1"`

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
```

**Bad:**
```python
def test_random():
    result = generate_random_id()
    assert len(result) == 10  # May fail if randomness changes
```

---

## Solution Issues

### Executable File Mode (OK)

**Note:** A new file mode of `100755` is fine for executable files. Do not flag this as an issue.

### Test Gaming

**Problem:** Parse and validate input format

**Bad Solution:**
```python
def validate(input):
    # Hardcoded for test cases
    if input == "test_case_1":
        return True
    if input == "test_case_2":
        return False
    # ... actual logic missing
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
    def validate(self, input):
        return len(input) > 0

class ValidatorFactory:
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

## Verdict Decision Guide

### REJECT If:
- Existing PR on GitHub solving same issue
- Made-up nonsensical feature
- Solution is trivial (< 2 lines)
- Tests can be passed without solving problem
- Fundamentally flawed concept

### REQUEST CHANGE If:
- Description too verbose (can be trimmed)
- Missing test coverage for stated requirements
- Over-specified technical details
- Minor alignment issues between description and tests
- Code quality issues that are fixable

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
List issues in order of importance:
1. Blockers (must fix)
2. Should fix (quality improvement)
3. Nice to have (minor polish)
