## Title

bugfix: packaging.utils.parse_wheel_filename must reject unsorted compressed tag sets per PEP 425

## Problem Brief

The wheel filename parser accepts filenames whose compressed tag sets are not sorted. A wheel name encodes python, abi, and platform as three dash separated fields. Each field may contain a dot separated compressed set, and each such set must be sorted. Filenames with unsorted compressed sets must be rejected with a clear error.

<!-- FEEDBACK: This is unnecessary -->
Valid, sorted inputs must continue to parse exactly as before, producing the same tags and values. Behavior must be deterministic and independent of environment.

## Agent Instructions

Fix validation in the wheel filename parser that enforces sorted compressed tag sets for the python, abi, and platform fields. 

<!-- FEEDBACK: This is repetitive -->
The validation must occur before tag expansion and must not alter parsing for already valid inputs.

When the build tag is absent, the returned build value must be an empty tuple. Preserve existing public types and exceptions. 

<!-- FEEDBACK: This is unnecessary. Including this creates confusion by suggesting that there are extra changes that aren't actually required. -->
Do not change how tags are generated or canonicalized; only add the required validation and keep all other behaviors stable.


## Technical Requirements

<!-- FEEDBACK: This is too detailed. Based on the codebase context, this function should be loctable just given "The wheel filename parser" -->
Location: src/packaging/utils.py

Public function parse_wheel_filename:

<!-- FEEDBACK: This is implied given the existing function already does this -->
Exceptions:
Must raise InvalidWheelFilename on invalid input; when rejecting unsorted compressed sets, the exception message must contain the substring unsorted compressed tag set.

<!-- FEEDBACK: I would rather have the tests not check for a given substring in this case. It seems there can be enough test cases to ensure that the function is treating all valid and invalid inputs correctly without specifically checking for this. -->

Inputs:
filename is a string that may include path separators; only the final component is considered. Only files ending in .whl are valid.

Parsing expectations:

Treat the name stem as the filename without the .whl suffix.

The final three dash separated components of the stem represent, in order: python tag set, abi tag set, platform tag set.

Each of these three components may be a single token or a dot separated compressed set.

If a component contains multiple tokens separated by dots, those tokens must be in lexicographic nondecreasing order using standard string comparison. If not, raise InvalidWheelFilename with an error message containing the unsorted compressed tag set.

Perform this validation prior to expanding tags or interpreting builds.

<!-- FEEDBACK: Developers should be able to already determine this from the existing code, since this part is not changing -->

Return values:

Project name: canonicalized string as currently produced by the module.

Version: an instance of packaging.version.Version parsed from the version field.

Build: when present, a tuple[int, str] where the first element is the numeric prefix and the second is the remainder; when absent, return an empty tuple.

Tags: a frozenset[Tag] representing all expanded tags derived from the validated python, abi, and platform fields. Tag formatting and expansion must remain unchanged.
