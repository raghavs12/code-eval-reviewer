# Example 3: Wheel Filename Parser Validation (Needs Improvement)

This example demonstrates a problem that has **too much unnecessary detail** and over-specifies the solution.

## Problem Overview

**Language**: Python
**Category**: Bugfix
**Difficulty**: Medium

## What Needs Improvement

This example shows common pitfalls in problem writing:

> **⚠️ Issue #1 - Redundant Information**: The problem description repeats implementation details that a competent developer could deduce from the context (e.g., explaining what "compressed tag sets" are in excessive detail).

> **⚠️ Issue #2 - Overly Specific Tests**: Tests check for exact error message substrings ("unsorted compressed tag set") which constrains implementation unnecessarily.

> **⚠️ Issue #3 - Unnecessary Technical Details**: Specifies internal implementation details like "validation must occur before tag expansion" when the behavior requirements are sufficient.

## Key Characteristics

- Addresses a real bug in packaging wheel filename parsing
- Based on actual PEP 425 specification
- BUT: Over-explains concepts the developer should know
- AND: Micromanages implementation approach
- ALSO: Tests implementation details rather than behavior

Compare this with examples 1 and 2 to see the difference between helpful guidance and over-prescription.
