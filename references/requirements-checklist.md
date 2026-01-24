# Requirements Checklist (R1-R5)

## R1 - GitHub Repository Requirements

### Validation Checks
| Check | Criteria | How to Verify |
|-------|----------|---------------|
| URL Valid | GitHub URL accessible | `curl -s -o /dev/null -w "%{http_code}" <url>` returns 200 |
| Active | ≥1 commit in last 12 months | Check repo commits page |
| Reputable | ≥500 stars | GitHub API or repo page |
| Language | TypeScript, JavaScript, or Python | Check repo language stats |
| License | Permissive (see below) | Check LICENSE file |
| No Existing Fix | No PR/issue already solving this | Search issues/PRs |

### Allowed Licenses
- MIT License
- BSD-1-Clause, BSD-2-Clause (all variants), BSD-3-Clause (all variants), BSD-4-Clause (all variants)
- Apache License 2.0 (all variants)
- Boost Software License 1.0
- Creative Commons Attribution (CC-BY 1.0-4.0)

## R2 - Dockerfile Requirements

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

### Docker Verification Commands
```bash
# Build image
docker build -t problem-test -f dockerfile .

# Run tests offline
docker run --network=none problem-test ./test.sh base
docker run --network=none problem-test ./test.sh new
```

## R3 - Problem Description Requirements

### Validation Checks
| Check | Criteria |
|-------|----------|
| Encoding | UTF-8 text |
| Original | Not AI-generated, not plagiarized |
| Not Malicious | No harmful content |
| No Existing Fix | GitHub issue not closed, no open PR |
| Issue URL | Provided if available |

### Red Flags
- Generic AI-style writing patterns
- Copy-pasted from documentation
- Problem already fixed in recent commits

## R4 - Test Patch Requirements

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

## R5 - Solution Patch Requirements

### Validation Checks
| Check | Criteria | Command |
|-------|----------|---------|
| Valid Patch | Applies cleanly | `git apply --check solution.patch` |
| No Conflicts | Works with test.patch in any order | Apply both ways |
| No New Deps | No internet-requiring dependencies | Inspect imports/requirements |
| Solution Only | No dockerfile changes | Inspect patch content |
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
