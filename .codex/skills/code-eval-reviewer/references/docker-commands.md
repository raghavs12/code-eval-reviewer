# Docker Verification Commands

Run these commands exactly and in order. Do not wait for user prompting.

---

## Phase 1: Test Patch Only (Pre-Solution)

```bash
# Clone and checkout
git clone <repo-url> repo
cd repo
git checkout <commit-hash>

# Apply test patch only
git apply test.patch

# Build Docker image
docker build -t shipd/<repo-name> -f Dockerfile .

# Run container with NO network
docker run -it --network=none shipd/<repo-name>

# Inside container:
sed -i 's/\r$//' ./test.sh    # Fix Windows line endings
./test.sh base                 # MUST PASS
./test.sh new                  # MUST FAIL
```

**Expected Results:**
- `./test.sh base` → Exit 0 (PASS)
- `./test.sh new` → Exit non-0 (FAIL)

---

## Phase 2: With Solution Patch

```bash
# Exit container, apply solution
git apply solution.patch

# Rebuild Docker image
docker build -t shipd/<repo-name> -f Dockerfile .

# Run container with NO network
docker run -it --network=none shipd/<repo-name>

# Inside container:
sed -i 's/\r$//' ./test.sh    # Fix Windows line endings
./test.sh base                 # MUST PASS
./test.sh new                  # MUST PASS
```

**Expected Results:**
- `./test.sh base` → Exit 0 (PASS)
- `./test.sh new` → Exit 0 (PASS)

---

## Quick Reference

| Phase | Command | Expected |
|-------|---------|----------|
| Pre-solution | `./test.sh base` | PASS |
| Pre-solution | `./test.sh new` | FAIL |
| Post-solution | `./test.sh base` | PASS |
| Post-solution | `./test.sh new` | PASS |

---

## Troubleshooting

### Windows Line Endings
```bash
sed -i 's/\r$//' test.sh
```

PowerShell alternative:
```powershell
$content = Get-Content test.sh -Raw
$content = $content -replace "`r`n", "`n"
[System.IO.File]::WriteAllText("test.sh", $content, [System.Text.UTF8Encoding]::new($false))
```

### Patch Conflicts
```bash
# Check if patch applies cleanly
git apply --check test.patch
git apply --check solution.patch

# Apply with 3-way merge if needed
git apply --3way test.patch
```

### Network Issues
Always use `--network=none` to ensure tests run offline:
```bash
docker run -it --network=none shipd/<repo-name>
```

### Build Cache Issues
```bash
# Force rebuild without cache
docker build --no-cache -t shipd/<repo-name> -f Dockerfile .
```

---

## Verification Checklist

- [ ] Repository cloned at correct commit
- [ ] Test patch applies cleanly
- [ ] Docker builds successfully
- [ ] Container runs with `--network=none`
- [ ] `./test.sh base` passes (pre-solution)
- [ ] `./test.sh new` fails (pre-solution)
- [ ] Solution patch applies cleanly
- [ ] Docker rebuilds successfully
- [ ] `./test.sh base` passes (post-solution)
- [ ] `./test.sh new` passes (post-solution)

---

## Important Notes

- Replace `<repo-name>` with actual repository name
- Replace `<repo-url>` with actual GitHub URL
- Replace `<commit-hash>` with actual commit hash
- Do NOT edit problem files during verification
- Always run container with `--network=none`
