# Examples (calibration)

Use these examples only to calibrate judgments about quality, conciseness, and test alignment.
Do not copy text verbatim into reviews.
Read the bundled examples in `references/examples/` for calibration.

## Example 1 (exemplar)

Use as the gold standard for:
- Clear, high-level problem brief that explains what and why without prescribing how.
- Agent instructions that set direction but leave implementation choices open.
- Behavior-focused tests that avoid implementation details.

## Example 2 (good, needs trimming)

Use to spot:
- Overly prescriptive "Proposed Solution" sections.
- Places where behavior can be specified without dictating implementation.
- Where constraints can be reduced to non-obvious interface details only.

## Example 3 (needs improvement)

Use to spot common issues:
- Redundant or overly detailed problem descriptions.
- Tests that assert exact error message substrings.
- Instructions that micromanage internal ordering or implementation timing.

## Bundled examples

- `references/examples/example-1-exemplar`
- `references/examples/example-2-good`
- `references/examples/example-3-needs-improvement`
