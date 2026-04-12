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
docker run --rm --network=none shipd/<repo-name> bash -lc '
  sed -i "s/\r$//" ./test.sh
  rm -f /tmp/base-results.xml
  ./test.sh --output_path /tmp/base-results.xml base
'

docker run --rm --network=none shipd/<repo-name> bash -lc '
  sed -i "s/\r$//" ./test.sh
  rm -f /tmp/new-results.xml
  ./test.sh --output_path /tmp/new-results.xml new
'
```

**Expected Results:**
- Base mode exits `0`
- New mode exits non-zero
- `/tmp/base-results.xml` and `/tmp/new-results.xml` both exist and are valid JUnit XML
- The XML written by new mode records at least one failure

---

## Phase 2: With Solution Patch

```bash
# Exit container, apply solution
git apply solution.patch

# Rebuild Docker image
docker build -t shipd/<repo-name> -f Dockerfile .

# Run container with NO network
docker run --rm --network=none shipd/<repo-name> bash -lc '
  sed -i "s/\r$//" ./test.sh
  rm -f /tmp/base-results.xml
  ./test.sh --output_path /tmp/base-results.xml base
'

docker run --rm --network=none shipd/<repo-name> bash -lc '
  sed -i "s/\r$//" ./test.sh
  rm -f /tmp/new-results.xml
  ./test.sh --output_path /tmp/new-results.xml new
'
```

**Expected Results:**
- Base mode exits `0`
- New mode exits `0`
- `/tmp/base-results.xml` and `/tmp/new-results.xml` both exist and are valid JUnit XML
- The XML written by both modes records zero failures

---

## Quick Reference

| Phase | Command | Expected |
|-------|---------|----------|
| Pre-solution | `./test.sh --output_path /tmp/base-results.xml base` | Exit 0 + valid XML |
| Pre-solution | `./test.sh --output_path /tmp/new-results.xml new` | Exit non-zero + valid XML with failures |
| Post-solution | `./test.sh --output_path /tmp/base-results.xml base` | Exit 0 + valid XML |
| Post-solution | `./test.sh --output_path /tmp/new-results.xml new` | Exit 0 + valid XML |

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

### Patch CRLF Normalization
If `git apply --check` fails only due to CRLF patch line endings, normalize the patch and retry. Treat this as environment normalization, not a submission issue:

```bash
sed -i 's/\r$//' test.patch
sed -i 's/\r$//' solution.patch
git apply --check test.patch
git apply --check solution.patch
```

PowerShell alternative:
```powershell
$p = Get-Content test.patch -Raw
$p = $p -replace "`r`n", "`n"
[System.IO.File]::WriteAllText("test.patch", $p, [System.Text.UTF8Encoding]::new($false))

$p2 = Get-Content solution.patch -Raw
$p2 = $p2 -replace "`r`n", "`n"
[System.IO.File]::WriteAllText("solution.patch", $p2, [System.Text.UTF8Encoding]::new($false))
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
docker run --rm --network=none shipd/<repo-name> bash -lc '<command>'
```

### Build Cache Issues
```bash
# Force rebuild without cache
docker build --no-cache -t shipd/<repo-name> -f Dockerfile .
```

### XML Validation
After each run, verify that the XML file exists and parses:

```bash
python - <<'PY'
import xml.etree.ElementTree as ET
ET.parse('/tmp/base-results.xml')
print('base xml ok')
ET.parse('/tmp/new-results.xml')
print('new xml ok')
PY
```

---

## Verification Checklist

- [ ] Repository cloned at correct commit
- [ ] Test patch applies cleanly
- [ ] Docker builds successfully
- [ ] Container runs with `--network=none`
- [ ] `./test.sh --output_path ... base` passes (pre-solution)
- [ ] `./test.sh --output_path ... new` fails (pre-solution)
- [ ] Both pre-solution modes still write JUnit XML
- [ ] Solution patch applies cleanly
- [ ] Docker rebuilds successfully
- [ ] `./test.sh --output_path ... base` passes (post-solution)
- [ ] `./test.sh --output_path ... new` passes (post-solution)
- [ ] Both post-solution modes write valid JUnit XML with zero failures

---

## Important Notes

- Replace `<repo-name>` with actual repository name
- Replace `<repo-url>` with actual GitHub URL
- Replace `<commit-hash>` with actual commit hash
- Do NOT edit problem files during verification
- Always run container with `--network=none`
- Missing XML is a blocker even if the exit code matches the expected pass/fail state
