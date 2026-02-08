# Requirements Checklist (R1-R5)

## R1 - GitHub Repository (Do this first. If it fails, reject immediately and still write feedback.md)

### Validation Checks
| Check | Criteria | How to Verify |
|-------|----------|---------------|
| URL Valid | GitHub URL accessible | Check URL loads |
| Active | ≥1 commit in last 12 months | Check repo commits page |
| Reputable | ≥500 stars | GitHub repo page |
| Language | TypeScript, JavaScript, Python, Go, or Rust | Check repo language stats |
| License | Permissive (see allowed list) | Check LICENSE file |
| No Existing Fix | No open or merged PR already solving this | Search issues/PRs |

### Existing PR/Issue Check (CRITICAL)
1. Pull repo + issue info from github-setup.md or Quick-Setup.txt
2. Search GitHub PRs (open + merged) for keywords in title/body
3. Search issues + PRs together with broader keywords
4. Open provided issue and look for linked PRs or references
5. In the issue, check whether it is marked fixed/resolved (labels, closing notes, linked PRs)
6. Skim results for anything that looks like the same feature
7. If likely match found, open that PR to confirm scope
8. If an issue already exists for the same problem, that is acceptable and does not need to be mentioned in the description
9. If there is an open PR or merged PR that fixes the same issue/problem, reject immediately
10. If license or reputability is unclear, contact Shipd team before accepting

---

## R2 - Dockerfile

### Required Structure
```dockerfile
FROM public.ecr.aws/x8v8d7g8/mars-base:latest
# ... setup commands ...
CMD ["/bin/bash"]  # or equivalent entrypoint
```

### Validation Checks
| Check | Criteria |
|-------|----------|
| Base Image | Must use `public.ecr.aws/x8v8d7g8/mars-base:latest` |
| Offline Tests | After build, tests must run without network |
| Standalone | Must work without test.patch or solution.patch applied |
| Entrypoint | Must have `/bin/bash` entrypoint |
| No Malicious Code | Review for suspicious commands |

---

## R3 - Problem Description

### Validation Checks
| Check | Criteria |
|-------|----------|
| Encoding | UTF-8 text |
| Original | Not AI-generated, not plagiarized |
| Not Malicious | No harmful content |
| No Existing Fix | GitHub issue not closed, no open PR |
| Issue URL | Optional; not required to be mentioned in the description |

### Red Flags
- Generic AI-style writing patterns
- Copy-pasted from documentation
- Problem already fixed in recent commits
- Problem describes already-merged or closed-issue behavior

---

## R4 - Test Patch

### Validation Checks
| Check | Criteria | Command |
|-------|----------|---------|
| Valid Patch | Applies cleanly | `git apply --check test.patch` |
| No Conflicts | Works with solution.patch in any order | Apply both ways |
| Test Only | No solution/dockerfile changes | Inspect patch content |
| Has test.sh | Script with base/new modes | Check file exists |
| Base Passes | `./test.sh base` exits 0 | Run at base commit |
| New Fails | `./test.sh new` exits non-0 without solution | Run at base commit |
| Offline | No internet required | `--network=none` |

### test.sh Expected Behavior
```bash
./test.sh base  # Run existing tests (regression check) - MUST PASS
./test.sh new   # Run new/modified tests - MUST FAIL without solution
```

---

## R5 - Solution Patch

### Validation Checks
| Check | Criteria | Command |
|-------|----------|---------|
| Valid Patch | Applies cleanly | `git apply --check solution.patch` |
| No Conflicts | Works with test.patch in any order | Apply both ways |
| No New Deps | No internet-requiring dependencies | Inspect imports/requirements |
| Solution Only | No dockerfile changes | Inspect patch content |
| Limited Test Changes | Only if old test was broken and relevant | Inspect patch content |
| Base Passes | `./test.sh base` exits 0 with solution | Run with both patches |
| New Passes | `./test.sh new` exits 0 with solution | Run with both patches |
| No Malicious | No suspicious code | Code review |

### Verification Sequence
```bash
# At base commit
git apply test.patch
git apply solution.patch
./test.sh base  # Must pass
./test.sh new   # Must pass
```

---

## Quick Reference

| Requirement | Key Question |
|-------------|--------------|
| R1 | Is the repo valid and is this problem novel? |
| R2 | Can we build and run tests offline? |
| R3 | Is the problem description original and clear? |
| R4 | Do tests fail without solution and pass baseline? |
| R5 | Does solution make all tests pass without regression? |
