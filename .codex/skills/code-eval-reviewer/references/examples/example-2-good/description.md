## Title

Fix Fraction Serialization Inconsistency in Python Mode

## Problem Brief

Pydantic currently serializes `Fraction` to strings in both Python and JSON modes, which is inconsistent with how `Decimal` is handled (objects in Python mode, strings in JSON mode). This makes working with different numeric types confusing. 
<!-- SUGGESTION: I would add here: `Fraction` should be handled the same way as `Decimal`. -->

There is also no built-in way to validate fractions with constraints like range checks or normalization, forcing users to write custom validators.

## Agent Instructions

Proposed Solution:

1. Fix Fraction Serialization

<!-- FEEDBACK: I think it should be enough to say something like "Fraction(4, 6) should be converted to '2/3' when serializing as strings". A competent developer should be able to figure everything else out -->
Match Decimal behavior:
- `model_dump()` --> `Fraction` objects
- `model_dump_json()` --> strings (e.g., `"1/3"`)
- Zero fractions should be serialize as `"0"` instead of `"0/1"` for instance
- Support parsing string inputs like `"1/3"`, `"-1/2"`

2. Add FractionField

<!-- FEEDBACK: This can be moved to just above the proposed solution section, and worded to begin as "Please add a FractionField type importable from `pydantic` with`: -->
Provide a dedicated field type importable from `pydantic` with:
- `normalize` (default `True`) - reduce to simplest form
- `gt`, `ge`, `lt`, `le`, `multiple_of` - constraint validation (accept `Fraction` objects)
- Standard `Field` params: `default`, `alias`, `description`, `title`, `examples`, `repr`

## Technical Requirements

