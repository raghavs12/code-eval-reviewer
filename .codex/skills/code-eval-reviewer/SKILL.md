---
name: code-eval-reviewer
description: Review Shipd MARS project submissions using problem inputs as source of truth, run Docker verification without prompting, score with the 1-7 reviewer rubric and 7/8/6 checklists, and write feedback.md in the repo root. Triggers on "review submission", "Shipd review", "MARS review", or when setup.sh/Problem-Description.txt/solution.patch files are provided.
---

# Shipd MARS Reviewer

## Focus
- Primary: problem quality and test completeness/fairness.
- Secondary: solution solvability, meaningful LOC/file-count thresholds, and padding/dead code checks.

## Operating Rule
Run the review stage by stage. Do not jump to the verdict early. Complete every required stage unless a stage explicitly says to stop on Reject.

## Optional Pre-Stage: Re-Review Check

### Goal
If `feedback.md` already exists in the review directory, treat the run as a re-review. Verify whether the previous requested changes were actually addressed, and also check for any new issues introduced in the updated submission files, before running the normal review.

### Actions
1. Detect re-review mode when `feedback.md` already exists in the review directory.
2. Parse the previously requested fixes or `Changes Required` items.
3. Classify each item as `ADDRESSED`, `PARTIAL`, or `NOT ADDRESSED`.
4. Explicitly check whether the updated `setup.sh`, `Problem-Description.txt`, or `solution.patch` introduced any new issues beyond the old feedback. If `setup.sh` embeds `test.patch`, `Dockerfile`, or `test.sh`, treat changes to those embedded artifacts as part of the same check.
5. Still run the full normal review after this check. Do not short-circuit the rest of the workflow.

### Decision Rules
- `Request Changes`: prior requested fixes are not fully addressed, or new fixable issues were introduced in the updated submission.
- `Continue`: no prior feedback was provided, or all requested changes were addressed.

### Required Notes
- Whether re-review mode was triggered
- Per-item incorporation status
- Re-review summary
- Any new issues introduced since the previous review

## Stage 1: Input Validation

### Goal
Confirm the review directory is reviewable and extract the base context.

### Actions
1. Find and parse `setup.sh`, `Problem-Description.txt`, and `solution.patch`.
2. Inspect `solutiondiff1.patch`, `solutiondiff2.patch`, and `solutiondiff3.patch`.
   - All three files are expected to be present.
   - Minimum one and maximum three will contain content.
   - Treat empty files as no-content placeholders.
3. If `test.patch` or `Dockerfile` are not present as separate files, extract them from `setup.sh`.
4. Treat `test.sh` as satisfied when it is created by `test.patch`.
5. Extract repository URL and commit hash.
6. Record any missing files.

### Decision Rules
- `Reject`: not used in this stage by itself.
- `Request Changes`: missing required files or malformed review directory.
- `Continue`: base inputs are present.

### Required Notes
- Repository URL
- Commit hash
- Presence/absence of required files, including whether `Dockerfile` and `test.patch` were extracted from `setup.sh` and whether `test.sh` is created by `test.patch`
- Number of passed agent solution diff files present and how many are non-empty

## Stage 2: Similarity Gate

### Goal
Reject duplicate or highly similar problems before spending time on deeper review.

### Actions
1. If multiple problem descriptions are provided, or the description includes a `Similar Problems` section, run the similarity prompt below.
2. Compare P1 against every additional problem statement.

### Decision Rules
- `Reject`: any problem is materially similar.
- `Continue`: no meaningful similarity found.

### Required Notes
- Whether similarity check ran
- Similarity findings if triggered

## Stage 3: Repository Gate

### Goal
Eliminate non-fixable repo-level failures early.

### Actions
1. Validate repository hard requirements from `references/creating-challenges.md`.
2. Check stars, activity, license, language, and public GitHub accessibility.
3. Search for open or merged PRs that already solve the same problem.

### Decision Rules
- `Reject`: wrong license, invalid repo, inactive repo, unsupported language, duplicate/existing PR, or other non-fixable repo-level failure.
- `Continue`: repo is valid.

### Required Notes
- Stars
- Last activity
- License
- Language
- Existing PR findings

## Stage 4: Problem Audit

### Goal
Review the problem statement as a standalone engineering spec.

### Actions
1. Score the 7 Problem checklist items from `references/creating-challenges.md`.
2. Extract explicit contracts (`must` / `should` statements) and split combined requirements.
3. Flag missing/implied contracts, ambiguous semantics, over-prescriptive schema/structure details, irrelevant context, and scope mismatches.

### Decision Rules
- `Request Changes`: any fixable problem-quality issue.
- `Continue`: problem statement is clear, self-contained, deterministic, and appropriately scoped.

### Required Notes
- Word count
- Explicit contracts
- Problem issues found

## Stage 5: Test Fairness Audit

### Goal
Ensure tests are complete, fair, behavioral, and actually aligned with the written problem.

### Actions
1. Score the 8 Tests checklist items from `references/creating-challenges.md`.
2. Run subpass `5A: Spec -> Test coverage`.
   - Build an explicit `Spec Requirement -> Covered by Test(s) -> Status` table.
   - Flag untested requirements.
3. Run subpass `5B: Test -> Spec fairness`.
   - Build an explicit `Test Assertion -> Traces to Spec Requirement -> Status` table.
   - Ask: could a partial or wrong implementation still pass?
   - For complex/stateful/merge-like behavior, ask whether the tests cover enough scenarios to rule out workaround or partially complete implementations.
4. Flag:
   - hidden requirements
   - stronger-than-spec expectations
   - representation-choice assertions (shape, ordering, normalization, canonicalization, inlining, flattening, exact counts)
   - multiple-valid-interpretation traps
   - loopholes that would allow workaround or partially complete implementations to pass
   - undocumented or hard-to-discover API/configuration requirements
   - internal leakage assertions
5. Apply a conservative public-surface/discoverability audit:
   - only flag if the evidence suggests the requirement is genuinely hard to infer from the problem and repo surface
   - distinguish documented public API from merely available implementation details

### Decision Rules
- `Request Changes`: any fixable fairness, determinism, alignment, or hidden-requirement issue.
- `Continue`: tests are fair and solver-discoverable.

### Required Notes
- Test fairness findings
- Spec -> test coverage table
- Test -> spec fairness table
- Alignment risks
- Workaround-solution risks
- Hidden/discoverability issues

## Stage 6: Docker Verification

### Goal
Confirm the submission behaves correctly in the required offline environment.

### Actions
1. Use the commands in `references/docker-commands.md`.
2. Verify:
   - base tests pass on base commit
   - new tests fail before solution
   - base tests pass with solution
   - new tests pass with solution
3. If `git apply --check` fails only due to CRLF line endings in patch files, normalize patch files to LF and retry. Treat this as environment normalization, not a submission issue.

### Decision Rules
- `Request Changes`: Docker build/test verification fails for a fixable reason.
- `Continue`: all expected verification states are correct.

### Required Notes
- Build result
- Pre-solution test results
- Post-solution test results
- Whether CRLF normalization was needed

## Stage 7: Solution Audit

### Goal
Confirm the solution is legitimate and satisfies the reviewer-side implementation constraints.

### Actions
1. Score the 6 Solution & Code checklist items from `references/creating-challenges.md`.
2. Verify:
   - non-empty meaningful hand-authored added lines >= 380
   - exclude test-file changes from meaningful and conservative LOC counts
   - meaningful file changes >= 3
   - all three `solutiondiff1.patch` to `solutiondiff3.patch` files must be checked
   - at least one of the three must be non-empty
   - compute the median across the non-empty passed agent solution diffs
   - the median meaningful LOC must be > 380
   - the median conservative LOC must be > 380
   - for each non-empty passed agent solution diff, report both meaningful LOC and conservative LOC in `feedback.md`
   - no generated-file inflation
   - exclude test files from meaningful and conservative LOC counting when they appear in `solution.patch`
   - blank lines and comment-only lines are always excluded; package lines, import block lines, and braces-only / formatting-only lines may still be counted, but report a conservative LOC figure separately and flag the patch if those structural lines are excessive
   - no padding / dead code / irrelevant changes
   - conservatively audit over-engineering:
     - ask whether the solution is much broader than the behavior described by the problem
     - ask whether the repo already appears to provide simpler infrastructure that the solution is rebuilding
     - ask whether large new helper/parser/printer/plumbing surfaces are clearly justified by the spec/tests
     - ask whether newly added helpers/types appear weakly referenced or effectively dead
     - ask whether the solution adds extra API/JSON fields not required by the spec/tests
     - ask whether the solution introduces registry/manager abstraction layers where the repo already uses a simpler collection pattern
     - ask whether the solution adds trivial wrapper helpers that only forward or stringify existing behavior
     - only flag over-engineering when multiple signals align; do not fail the review on a single weak clue
   - no suspicious API breakage unless required

### Decision Rules
- `Request Changes`: fixable solution-quality issues, insufficient meaningful LOC/file count, padding, or regressions.
- `Continue`: solution is legitimate and meets reviewer thresholds.

### Required Notes
- Meaningful LOC
- Conservative LOC
- Structural/non-logic lines counted in meaningful LOC
- Meaningful file count
- Generated LOC excluded
- Test-file LOC excluded from meaningful/conservative counts
- Passed agent solution diff median meaningful LOC
- Passed agent solution diff median conservative LOC
- Over-engineering / reuse / low-reference signals when present
- Passed agent solution diff LOC summaries when provided
- Solution issues found

## Stage 8: Decision Synthesis

### Goal
Produce the final verdict only after every prior stage has run.

### Actions
1. Assign the overall quality score using `references/reviewer-rubric-2026.md`.
2. Classify issues:
   - non-fixable issues -> `Reject`
   - fixable issues -> `Request Changes`
   - no issues and quality score >= 5 -> `Approve`
3. Write `feedback.md` in the repo root using `references/feedback-template.md`.
4. Include:
   - author-facing feedback
   - `Ambiguity Flags`
   - `Prescriptiveness Flags`
   - `Passed Agent Solution Diffs`
   - `Spec-Test Alignment`
   - `Changes Required`
   - checklist selections
   - quality score
   - reasoning
   - concrete fixes for any issue that can be fixed

### Decision Rules
- `Approve`: no fixable issues and quality score >= 5.
- `Request Changes`: any fixable issue remains.
- `Reject`: any non-fixable issue remains.

### Required Notes
- Final decision
- Quality score
- Fix suggestions

## Similarity Prompt

Use this prompt when multiple problem descriptions are provided or a `Similar Problems` section is present.

```text
Analyze the overlap between the following problem statements and report quantitative similarity findings across three dimensions:

Behavioural Match Percentage
Implementation-Specific Match Percentage
Requirement-Specific Match Percentage

For each dimension:
- Clearly list shared vs divergent aspects.
- Use concrete counts (for example 5/7, 4/8) to justify percentages.
- Call out unique or scope-expanding requirements separately.
- Provide a short interpretation explaining what the percentage implies (same problem, partial overlap, or different scope).

P1:
[Paste P1]

P2:
[Paste P2]

P3:
[Paste P3]
```

## References

- `references/creating-challenges.md` - Hard requirements and checklists (7/8/6)
- `references/reviewer-rubric-2026.md` - Quality score rubric (1-7)
- `references/feedback-template.md` - Exact output structure
- `references/allowed-licenses.md` - Permissive license list
- `references/docker-commands.md` - Exact verification commands
