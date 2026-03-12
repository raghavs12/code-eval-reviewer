# Reviewer Rubric (2026)

Use this rubric to assign the overall quality score (1-7).

## Rating 7 - Exceptional
Problem Spec
- Fully deterministic, zero ambiguity.
- Concise and non-prescriptive.
- Perfectly aligned with tests.
- No irrelevant context.
- Clean structure and formatting.

Tests
- Deterministic and rock-solid.
- Strong, precise assertions.
- Covers required behavior and edge cases cleanly.
- No redundancy.
- No internal leakage.

Solution
- Implements all requirements exactly.
- Zero unnecessary changes.
- Fully idiomatic and aligned with repo patterns.
- No dead code, no speculative logic, no unrelated edits.

## Rating 6 - Strong
Problem Spec
- Extremely clear, with only minor verbosity, slight prescriptiveness, or small phrasing improvements possible.
- Alignment with tests is tight.

Tests
- Deterministic.
- Possibly slight redundancy or minor stylistic inconsistency.
- Edge case coverage could be slightly improved.
- Not missing any major tests.

Solution
- Complete and correct.
- Minor stylistic issues or tiny simplification opportunities.
- Fully aligned with repo philosophy.
- No structural concerns.

## Rating 5 - Good (Approvable)
Problem Spec
- Clear and complete but somewhat verbose, prescriptive, or structurally imperfect.
- Alignment with tests is tight.

Tests
- Deterministic and valid.
- Some redundancy or uneven elegance.
- Assertions are correct but occasionally not maximally sharp.
- Poor edge case coverage.

Solution
- Meets all requirements.
- May feel slightly clunky or mildly over-engineered.
- Minor pattern deviations or small unnecessary complexity, but no regressions or unrelated edits.

## Rating 4 - Borderline (Needs Minor Revisions)
Problem Spec
- Noticeable ambiguity, structural awkwardness, or partial misalignment with tests.
- Possibly somewhat prescriptive.
- Would benefit from clarification before approval.

Tests
- Deterministic but bloated, missing some edge cases, or containing weak assertions.
- Structural mismatch with repo conventions.
- Requires changes before approval.

Solution
- Functionally close but includes awkward design choices, questionable edits, minor regression risk, or noticeable pattern violations.
- Requires changes before approval.

## Rating 3 - Major Quality Issues
Problem Spec
- Ambiguities present. Incomplete or loosely defined requirements.
- Clear misalignment with tests.

Tests
- Weak assertions, incomplete behavior coverage, structural issues, or determinism concerns.
- Tests may partially fail to enforce spec correctly.

Solution
- Incomplete implementation, design inconsistencies, visible AI slop, or significant deviation from repo patterns.
- Heavy revision required.

## Rating 2 - Fundamentally Broken
Problem Spec
- Missing key requirements or major conceptual confusion.

Tests
- Tests do not properly fail on base, are flaky, or violate determinism rules.

Solution
- Major requirements missing, conceptual misunderstanding, regressions, or structural breakage.
- Substantial rewrite required.

## Rating 1 - Rejected
Problem Spec
- Duplicate, already publicly solved, invalid scope, or violates core submission rules.

Tests
- Invalid patch, conflicts, not runnable, or violates hard requirements.

Solution
- Invalid patch, conflicts with tests, breaks base tests, violates core constraints, or is fundamentally out of scope.

## Reviewer Shortcut (4-7 Decision Aid)
Ask: "How many quality comments would I realistically leave?"
- 0 meaningful improvement comments -> 7
- 1-3 minor polish suggestions -> 6
- Several quality improvement comments, but still approvable -> 5
- Requires changes before merge -> 4