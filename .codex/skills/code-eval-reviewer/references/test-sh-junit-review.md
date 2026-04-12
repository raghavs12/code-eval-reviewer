# test.sh And JUnit Review

Use this file when reviewing `test.patch` and Docker verification behavior.

## Required contract
- `test.sh` accepts `--output_path <path>` and exactly one mode: `base` or `new`
- `base` runs the regression suite and must pass on the base commit
- `new` runs the new or modified tests and must fail on the base commit
- Both modes must write JUnit XML to the requested output path

## Acceptable XML generation
- Native runner/reporting support such as `pytest --junitxml`, `jest-junit`, `vitest --reporter=junit`, `go-junit-report`, `mocha-junit-reporter`, `rspec_junit_formatter`
- A standard converter from a stable machine-readable runner output, such as TAP piped through `tap-xunit`, when native JUnit is unavailable

## Unacceptable XML generation
- Hand-built XML strings in shell
- Inline Node/Python scripts that manually write `<testsuite>` / `<testcase>` output
- Custom converters that are not standard test-report tooling

## Failure-path requirement
- A failing test run is not enough by itself. The XML file must still appear.
- `set -e` is only acceptable if the script still guarantees XML emission on a failing test run.
- Explicit status capture such as `runner || STATUS=$?` is acceptable.

## Base-test exclusions
- Exclusions in base mode need concrete reasons.
- The reason should explain why the test is invalid in the sandbox, not just that it is flaky.
- Do not exclude tests in the part of the repo touched by the task unless there is a real environment blocker.
