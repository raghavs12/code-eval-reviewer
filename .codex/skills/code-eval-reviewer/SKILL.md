---
name: code-eval-reviewer
description: Review Shipd MARS project submissions using problem inputs as source of truth, run Docker verification without prompting, score with the 1-7 reviewer rubric and 7/8/6 checklists, and write feedback.md in the repo root. Triggers on "review submission", "Shipd review", "MARS review", or when setup.sh/Problem-Description.txt/solution.patch files are provided.
---

# Shipd MARS Reviewer

## Focus
- Primary: problem quality and test completeness/fairness.
- Secondary: solution solvability, LOC threshold, and padding/dead code checks.

## Workflow Overview
1. Parse inputs: setup.sh, Problem-Description.txt, test.patch, solution.patch, Dockerfile, test.sh.
2. Similarity gate: if multiple problem descriptions are provided or the problem description includes a "Similar Problems" section listing other problems, run the similarity prompt. If any similarity is detected, stop and write feedback.md with decision Reject.
3. Repository validation (hard requirements): GitHub URL + commit, recent activity, stars, license, language, no open or merged PR that already fixes the same problem. If any fail, reject.
4. Docker verification: run base/new tests pre-solution, then with solution. If `git apply --check` fails only due to CRLF line endings in patch files, normalize patch files to LF and retry. Treat this as an environment normalization step, not a submission issue.
5. Evaluate Problem checklist (7) and Tests checklist (8) from references/creating-challenges.md.
6. Spec/Test alignment audit (required):
   - Extract explicit contracts (must/should) and split combined statements.
   - Flag implied contracts and over-prescriptive schemas.
   - Map each test to one or more contracts; flag hidden requirements.
   - Flag ambiguous semantics and internal leakage assertions.
7. Evaluate Solution & Code checklist (6) with emphasis on solvability, LOC >= 380, and padding/dead code. Agent-run thresholds are externally verified.
8. Assign overall quality score 1-7 using references/reviewer-rubric-2026.md.
9. Write feedback.md in the repo root using references/feedback-template.md. Include Reasoning in feedback.md only (no review_log.md).

## Input Files

| File | Contents |
|------|----------|
| setup.sh | Repo URL, commit hash, test patch, Dockerfile, test.sh |
| Problem-Description.txt | Task brief, requirements, test assumptions |
| test.patch | Test patch (git diff format) |
| solution.patch | Solution patch (git diff format) |

## Similarity Prompt

Use this prompt when multiple problem descriptions are provided or a "Similar Problems" section is present. If any similarity is detected, stop and reject.

```
Analyze the overlap between the following problem statements and report quantitative similarity findings across three dimensions:

Behavioural Match Percentage

Implementation-Specific Match Percentage

Requirement-Specific Match Percentage

For each dimension:
Clearly list shared vs divergent aspects.

Use concrete counts (for example 5/7, 4/8) to justify percentages.

Call out unique or scope-expanding requirements separately.

Provide a short interpretation explaining what the percentage implies (same problem, partial overlap, or different scope).

P1:
[Paste P1]

P2:
[Paste P2]

P3:
[Paste P3]
```

## Hard Requirements

See references/creating-challenges.md for all hard requirements and checklist items. If any hard requirement fails, reject.

## Docker Verification

Use the exact commands in references/docker-commands.md. Do not prompt the user.

## Scoring and Decision

- Overall quality score is 1-7 using references/reviewer-rubric-2026.md.
- Approve: no fixable issues and quality score >= 5.
- Request Changes: fixable issues (test determinism, alignment, missing patches, Docker failures, weak specs, etc).
- Reject: non-fixable issues only (duplicate/similar problem, wrong license, invalid repo, or existing PR that already fixes the problem).

## Output

- Use references/feedback-template.md exact format.
- Mark selected decision and checklist options explicitly.
- ASCII only.

## References

- references/creating-challenges.md - Hard requirements and checklists (7/8/6)
- references/reviewer-rubric-2026.md - Quality score rubric (1-7)
- references/feedback-template.md - Exact output structure
- references/allowed-licenses.md - Permissive license list
- references/docker-commands.md - Exact verification commands
