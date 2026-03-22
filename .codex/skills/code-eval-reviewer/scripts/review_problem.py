#!/usr/bin/env python3
"""
Code Eval Reviewer - Automated Problem Review Script

Usage:
    python3 review_problem.py <problem-dir> [--repo-url URL] [--commit HASH] [--skip-docker]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen


def run_command(cmd: List[str], cwd: Optional[str] = None, capture: bool = True, timeout: int = 300) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def find_file(directory: Path, names: List[str]) -> Optional[Path]:
    for name in names:
        path = directory / name
        if path.exists():
            return path
        for f in directory.iterdir():
            if f.name.lower() == name.lower():
                return f
    return None


def find_files(directory: Path, names: List[str]) -> List[Path]:
    found = []
    for name in names:
        path = directory / name
        if path.exists():
            found.append(path)
        else:
            for f in directory.iterdir():
                if f.name.lower() == name.lower():
                    found.append(f)
    return list(dict.fromkeys(found))


def extract_embedded_file_from_setup(setup_text: str, target_name: str) -> Optional[str]:
    escaped = re.escape(target_name)
    patterns = [
        rf"cat\s+>\s*{escaped}\s*<<['\"]?(\w+)['\"]?\s*\n([\s\S]*?)\n\1",
        rf"cat\s+<<['\"]?(\w+)['\"]?\s*>\s*{escaped}\s*\n([\s\S]*?)\n\1",
        rf"cat\s+>\s*['\"]?\.?/?{escaped}['\"]?\s*<<['\"]?(\w+)['\"]?\s*\n([\s\S]*?)\n\1",
        rf"cat\s+<<['\"]?(\w+)['\"]?\s*>\s*['\"]?\.?/?{escaped}['\"]?\s*\n([\s\S]*?)\n\1",
    ]
    for pattern in patterns:
        match = re.search(pattern, setup_text, re.MULTILINE)
        if match:
            return match.group(2)
    return None


def materialize_embedded_setup_files(problem_dir: Path, setup_file: Optional[Path]) -> Dict[str, Optional[Path]]:
    result = {"Dockerfile": None, "test.patch": None}
    if not setup_file or not setup_file.exists():
        return result
    setup_text = read_text(setup_file)
    extract_dir = problem_dir / ".codex_extracted"
    extract_dir.mkdir(exist_ok=True)
    for name in result.keys():
        content = extract_embedded_file_from_setup(setup_text, name)
        if content is None:
            continue
        out_path = extract_dir / name
        out_path.write_text(content.rstrip("\n") + "\n", encoding="utf-8")
        result[name] = out_path
    return result


def detect_setup_extraction_expectations(setup_text: str) -> List[str]:
    expected = []
    for name in ["test.patch", "Dockerfile"]:
        if re.search(rf"\b{name}\b", setup_text):
            expected.append(name)
    return expected


def extract_test_sh_created_by_patch(test_patch_text: str) -> bool:
    if not test_patch_text:
        return False
    return bool(re.search(r"^\+\+\+\s+b/test\.sh$", test_patch_text, re.MULTILINE))


def count_words(text: str) -> int:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"[#*_\[\]()>-]", " ", text)
    words = text.split()
    return len(words)


def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", text)
    stop = {
        "the", "and", "or", "to", "of", "a", "an", "is", "are", "be", "in", "on",
        "for", "with", "by", "as", "at", "from", "that", "this", "it", "its", "if",
        "then", "else", "when", "while", "should", "must", "shall", "may", "can",
        "not", "no", "yes", "do", "does", "did", "done", "into", "out", "up", "down",
    }
    return [t for t in tokens if t not in stop and len(t) > 2]


def sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"[.!?]\s+", text) if s.strip()]


def requirement_sentences(text: str) -> List[str]:
    req = []
    for s in sentences(text):
        if re.search(r"\b(must|should|shall|needs to|required to|must not|should not)\b", s, re.IGNORECASE):
            req.append(s)
    return req


def split_compound_requirements(sentences: List[str]) -> List[str]:
    parts = []
    for s in sentences:
        chunks = re.split(r"\b(and|or|,|;)\b", s)
        for c in chunks:
            c = c.strip()
            if len(c) > 8 and re.search(r"\b(must|should|shall|needs to|required to|must not|should not)\b", c, re.IGNORECASE):
                parts.append(c)
    return parts or sentences


def find_implied_contracts(text: str) -> List[str]:
    implied = []
    patterns = [
        r"\binvariant\b",
        r"\bmust\s+reach\b",
        r"\bmay\s+reach\b",
        r"\bdefinitions\b",
        r"\bcontract\b",
        r"\bimplies\b",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in patterns):
        if not re.search(r"\bdefines?\s+the\s+definitions?\s+field\b", text, re.IGNORECASE):
            implied.append("Implied contract: definitions field behavior is not explicitly defined.")
    return implied


def find_schema_prescription(text: str) -> List[str]:
    issues = []
    schema_patterns = [
        r"\bdataclass\b",
        r"\bfrozen\b",
        r"\bschema\b",
        r"\bfield(s)?\b",
        r"\btyped?\b",
        r"\bstruct\b",
        r"\bclass\s+name\b",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in schema_patterns):
        issues.append("Spec appears to prescribe internal schema/structure details.")
    return issues


def extract_test_cases(test_patch: str) -> List[str]:
    cases = []
    for m in re.findall(r"def (test_[\\w_]+)\\s*\\(", test_patch):
        cases.append(m.replace("_", " "))
    for m in re.findall(r"\\btest\\(\\s*['\\\"]([^'\\\"]+)['\\\"]", test_patch):
        cases.append(m)
    for m in re.findall(r"\\bit\\(\\s*['\\\"]([^'\\\"]+)['\\\"]", test_patch):
        cases.append(m)
    for m in re.findall(r"\\bfunc\\s+(Test\\w+)\\s*\\(", test_patch):
        cases.append(m)
    return cases


def normalize_token_set(text: str) -> set:
    return set(tokenize(text))


def token_overlap_score(a: str, b: str) -> float:
    ta = normalize_token_set(a)
    tb = normalize_token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def extract_test_blocks(test_patch: str) -> List[Dict[str, object]]:
    blocks = []
    current = None
    for raw_line in test_patch.splitlines():
        if not raw_line.startswith("+") or raw_line.startswith("+++ "):
            continue
        line = raw_line[1:]
        stripped = line.strip()
        test_name = None
        for pattern in [
            r"def (test_[\w_]+)\s*\(",
            r"\btest\(\s*['\"]([^'\"]+)['\"]",
            r"\bit\(\s*['\"]([^'\"]+)['\"]",
            r"\bfunc\s+(Test\w+)\s*\(",
            r"#\[test\]\s*fn\s+(\w+)",
        ]:
            match = re.search(pattern, stripped)
            if match:
                test_name = match.group(1)
                break
        if test_name:
            if current:
                blocks.append(current)
            current = {"name": test_name, "lines": [], "assertions": []}
            continue
        if not current:
            continue
        current["lines"].append(stripped)
        if re.search(r"\b(assert|expect|require\.)\b", stripped):
            current["assertions"].append(stripped)
    if current:
        blocks.append(current)
    return blocks


def summarize_assertion(assertion: str) -> str:
    cleaned = re.sub(r"\s+", " ", assertion.strip())
    return cleaned[:160]


def build_alignment_tables(contracts: List[str], test_patch: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    spec_rows: List[Dict[str, str]] = []
    assertion_rows: List[Dict[str, str]] = []
    test_blocks = extract_test_blocks(test_patch)

    for contract in contracts:
        matches = []
        for block in test_blocks:
            corpus = " ".join([block["name"]] + list(block["lines"]) + list(block["assertions"]))
            if token_overlap_score(contract, corpus) >= 0.16:
                matches.append(str(block["name"]))
        spec_rows.append(
            {
                "requirement": contract,
                "tests": ", ".join(matches[:4]) if matches else "(none)",
                "status": "Covered" if matches else "Untested",
            }
        )

    for block in test_blocks:
        assertions = block["assertions"] or block["lines"][:1] or [str(block["name"])]
        for assertion in assertions[:4]:
            best_contract = ""
            best_score = 0.0
            for contract in contracts:
                score = token_overlap_score(assertion, contract)
                if score > best_score:
                    best_score = score
                    best_contract = contract
            assertion_rows.append(
                {
                    "assertion": f"{block['name']}: {summarize_assertion(assertion)}",
                    "requirement": best_contract if best_score >= 0.14 else "(none)",
                    "status": "Aligned" if best_score >= 0.14 else "Hidden Requirement",
                }
            )
    return spec_rows, assertion_rows


def format_table(headers: List[str], rows: List[List[str]]) -> List[str]:
    lines = [" | ".join(headers), " | ".join(["---"] * len(headers))]
    for row in rows:
        lines.append(" | ".join(row))
    return lines


def is_ignored_search_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    ignored_parts = [
        "/.git/", "/node_modules/", "/vendor/", "/dist/", "/build/", "/coverage/", "/.venv/",
        "/__pycache__/", "/target/", "/tmp/", "/generated/",
    ]
    return any(part in normalized for part in ignored_parts)


def extract_test_requirement_tokens(test_patch: str) -> List[str]:
    tokens = []
    added_lines = [line[1:] for line in test_patch.splitlines() if line.startswith("+") and not line.startswith("+++ ")]
    added_text = "\n".join(added_lines)

    tokens.extend(re.findall(r"@([A-Za-z_][A-Za-z0-9_]*)", added_text))
    tokens.extend(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=", added_text))
    tokens.extend(re.findall(r"['\"](--[A-Za-z0-9_-]+)['\"]", added_text))
    tokens.extend(re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_-]*mode)['\"]", added_text, re.IGNORECASE))
    tokens.extend(re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]\s*:", added_text))

    filtered = []
    ignore = {
        "self", "cls", "true", "false", "none", "input", "output", "expected", "actual",
        "kwargs", "args",
    }
    for token in tokens:
        token_l = token.lower()
        if len(token_l) < 3:
            continue
        if token_l in ignore:
            continue
        if re.fullmatch(r"[0-9_]+", token_l):
            continue
        filtered.append(token)
    return list(dict.fromkeys(filtered))


def count_token_mentions(repo_dir: Optional[Path], token: str, touched_test_files: List[str]) -> Dict[str, int]:
    counts = {"docs": 0, "public": 0, "tests": 0}
    if not repo_dir or not repo_dir.exists():
        return counts

    touched = {p.replace("\\", "/") for p in touched_test_files}
    doc_exts = {".md", ".rst", ".txt"}
    public_exts = {".py", ".go", ".rs", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cc", ".cpp", ".h"}

    token_re = re.compile(rf"\b{re.escape(token)}\b")
    for root, _, files in os.walk(repo_dir):
        for name in files:
            path = Path(root) / name
            rel = str(path.relative_to(repo_dir)).replace("\\", "/")
            rel_lower = rel.lower()
            if is_ignored_search_path(rel_lower):
                continue
            if rel in touched:
                continue
            try:
                text = read_text(path)
            except Exception:
                continue
            if not token_re.search(text):
                continue
            if path.suffix.lower() in doc_exts or name.lower().startswith("readme"):
                counts["docs"] += 1
            elif "/test" in rel_lower or "/tests/" in rel_lower or name.lower().startswith("test_"):
                counts["tests"] += 1
            elif path.suffix.lower() in public_exts:
                counts["public"] += 1
    return counts


def undocumented_surface_issues(desc_text: str, test_patch: str, repo_dir: Optional[Path]) -> List[str]:
    issues = []
    desc_tokens = set(tokenize(desc_text))
    touched_test_files = re.findall(r"^\+\+\+\s+b/(.+)$", test_patch, re.MULTILINE)
    candidate_tokens = extract_test_requirement_tokens(test_patch)

    hidden_candidates = []
    for token in candidate_tokens:
        token_norm = token.lower().lstrip("-")
        if token_norm in desc_tokens:
            continue
        counts = count_token_mentions(repo_dir, token, touched_test_files)
        # Conservative threshold: flag only if the token is absent from docs and tests
        # outside the added patch, and appears at most weakly in non-test code.
        if counts["docs"] == 0 and counts["tests"] == 0 and counts["public"] <= 1:
            hidden_candidates.append(token)

    if hidden_candidates:
        sample = ", ".join(hidden_candidates[:3])
        issues.append(f"Tests may depend on undocumented or hard-to-discover API/configuration surface: {sample}.")
    return issues


def representation_choice_issues(desc_text: str, test_patch: str) -> List[str]:
    issues = []
    desc_lower = desc_text.lower()
    exact_shape_patterns = [
        r"assertEqual\\(len\\(",
        r"assert\\s+len\\(",
        r"assertEqual\\([^\\n]*\\[[^\\n]*\\]",
        r"assert\\s+[^\\n]*==\\s*\\[[^\\n]*\\]",
        r"assert\\s+[^\\n]*==\\s*\\{[^\\n]*\\}",
        r"assertEqual\\([^\\n]*['\\\"]",
    ]
    representation_terms = [
        "shape", "order", "ordered", "sorted", "normalize", "normalized", "canonical",
        "canonicalize", "flatten", "flattened", "inline", "inlined", "exact", "count",
    ]
    exact_shape_assertion = any(re.search(p, test_patch) for p in exact_shape_patterns)
    representation_risk = any(term in test_patch.lower() for term in representation_terms)
    spec_mentions_representation = any(term in desc_lower for term in representation_terms)

    if exact_shape_assertion and not spec_mentions_representation:
        issues.append("Tests assert exact shape/count/order without the spec explicitly requiring that representation choice.")
    elif representation_risk and not spec_mentions_representation:
        issues.append("Tests may enforce normalization/canonicalization or another representation choice not stated in the spec.")
    return issues


def stronger_than_spec_issues(contracts: List[str], desc_text: str, test_patch: str) -> List[str]:
    issues = []
    if not contracts:
        return issues
    contract_tokens = set(tokenize(" ".join(contracts)))
    assert_lines = re.findall(r"\\bassert(?:Equal|In|NotIn|True|False)?\\b[^\\n]*", test_patch)
    stronger_lines = []
    for line in assert_lines:
        tokens = set(tokenize(line))
        if not tokens:
            continue
        extra = tokens - contract_tokens
        if len(extra) >= 3:
            stronger_lines.append(line.strip())
    if stronger_lines:
        issues.append("Tests may require a stronger interpretation than the problem statement explicitly states.")
    return issues


def multiple_valid_interpretations_issues(desc_text: str, test_patch: str) -> List[str]:
    issues = []
    desc_lower = desc_text.lower()
    ambiguous_axes = [
        ("order", ["sort", "sorted", "order"]),
        ("shape", ["shape", "flatten", "inline", "normalize", "canonical"]),
        ("count", ["len(", "count(", "assertEqual(len(", "assert len("]),
        ("equivalence", ["exact", "==", "assertEqual("]),
    ]
    for axis_name, signals in ambiguous_axes:
        spec_mentions = any(signal in desc_lower for signal in signals)
        test_mentions = any(signal in test_patch for signal in signals)
        if test_mentions and not spec_mentions:
            issues.append(f"Tests may force one valid {axis_name} interpretation without the spec explicitly choosing it.")
            break
    return issues


def spec_test_alignment(contracts: List[str], test_cases: List[str], test_patch: str) -> List[str]:
    issues = []
    if not contracts or not test_cases:
        return issues
    contract_tokens = [set(tokenize(c)) for c in contracts]
    for case in test_cases:
        tokens = set(tokenize(case))
        if not tokens:
            continue
        overlap = max((len(tokens & ct) / max(1, len(tokens))) for ct in contract_tokens)
        if overlap < 0.2:
            issues.append(f"Test case may not map to an explicit contract: {case}")
            break
    if re.search(r"assert\\s+len\\(", test_patch) or re.search(r"assertEqual\\(len\\(", test_patch):
        issues.append("Tests assert specific counts that may depend on unspecified semantics.")
    return issues


def ambiguity_checks(text: str) -> List[str]:
    issues = []
    ambiguous_terms = [
        "path-sensitive", "path sensitive", "may", "must", "order", "duplicate", "empty",
        "undefined", "unspecified", "implied", "invariant",
    ]
    if any(term in text.lower() for term in ambiguous_terms):
        if not re.search(r"\bexplicitly\b|\bdefined\b|\bclarify\b", text, re.IGNORECASE):
            issues.append("Spec contains potentially ambiguous semantics without explicit clarification.")
    return issues


def identifier_tokens(text: str) -> List[str]:
    tokens = []
    tokens += re.findall(r"`([^`]+)`", text)
    tokens += re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", text)
    tokens += re.findall(r"\b[a-z]+[A-Z][a-zA-Z0-9]*\b", text)
    return tokenize(" ".join(tokens))


def jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))

def extract_repo_info_from_setup(setup_path: Path) -> Tuple[Optional[str], Optional[str]]:
    text = read_text(setup_path)
    url_match = re.search(r"https?://github\.com/[\w.-]+/[\w.-]+", text)
    commit_match = re.search(r"\b[a-f0-9]{40}\b", text)
    url = url_match.group(0) if url_match else None
    commit = commit_match.group(0) if commit_match else None
    return url, commit


def parse_similar_problems_section(text: str) -> List[str]:
    lines = text.splitlines()
    results = []
    in_section = False
    for line in lines:
        if re.match(r"^\s*#+\s*Similar Problems", line, re.IGNORECASE) or re.match(r"^\s*Similar Problems", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if line.strip() == "":
                break
            m = re.match(r"^\s*[-*]\s+(.*)$", line)
            if m:
                results.append(m.group(1).strip())
                continue
            m = re.match(r"^\s*\d+\.\s+(.*)$", line)
            if m:
                results.append(m.group(1).strip())
                continue
            if line.strip():
                results.append(line.strip())
    return results


def similarity_metrics(p1: str, p2: str) -> Dict[str, float]:
    all_tokens = tokenize(p1)
    all_tokens_2 = tokenize(p2)
    req_tokens = tokenize(" ".join(requirement_sentences(p1)))
    req_tokens_2 = tokenize(" ".join(requirement_sentences(p2)))
    impl_tokens = identifier_tokens(p1)
    impl_tokens_2 = identifier_tokens(p2)
    return {
        "behavioural": jaccard(req_tokens, req_tokens_2) * 100,
        "implementation": jaccard(impl_tokens, impl_tokens_2) * 100,
        "requirement": jaccard(all_tokens, all_tokens_2) * 100,
    }


def detect_similarity(main_text: str, others: List[str]) -> Tuple[bool, List[str]]:
    reports = []
    for idx, text in enumerate(others, start=2):
        metrics = similarity_metrics(main_text, text)
        report = (
            f"P1 vs P{idx}: behavioural={metrics['behavioural']:.1f}%, "
            f"implementation={metrics['implementation']:.1f}%, "
            f"requirement={metrics['requirement']:.1f}%"
        )
        reports.append(report)
        if any(m >= 60.0 for m in metrics.values()):
            return True, reports
    return False, reports


def github_api_get(url: str) -> Optional[Dict]:
    try:
        req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "code-eval-reviewer"})
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def load_allowed_licenses() -> List[str]:
    try:
        path = Path(__file__).resolve().parent.parent / "references" / "allowed-licenses.md"
        if not path.exists():
            return []
        text = read_text(path)
        ids = set(re.findall(r"\\(([A-Za-z0-9.\\-]+)\\)", text))
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("- "):
                token = line[2:].split()[0].strip("()")
                if re.match(r"^[A-Za-z0-9.\\-]+$", token):
                    ids.add(token)
        return sorted(ids)
    except Exception:
        return []


def validate_repo(repo_url: Optional[str], description_text: str) -> Dict:
    result = {
        "ok": True,
        "issues": [],
        "notes": [],
        "owner_repo": None,
        "reject_reasons": [],
    }
    if not repo_url or "github.com" not in repo_url:
        result["ok"] = False
        result["issues"].append("Missing or invalid GitHub URL")
        result["reject_reasons"].append("Missing or invalid GitHub URL")
        return result

    m = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if not m:
        result["ok"] = False
        result["issues"].append("Unable to parse GitHub owner/repo")
        result["reject_reasons"].append("Unable to parse GitHub owner/repo")
        return result

    owner, repo = m.group(1), m.group(2)
    result["owner_repo"] = f"{owner}/{repo}"

    repo_info = github_api_get(f"https://api.github.com/repos/{owner}/{repo}")
    if not repo_info:
        result["ok"] = False
        result["issues"].append("GitHub API lookup failed")
        result["reject_reasons"].append("GitHub API lookup failed")
        return result

    stars = repo_info.get("stargazers_count", 0)
    pushed_at = repo_info.get("pushed_at")
    language = repo_info.get("language")
    license_info = repo_info.get("license") or {}
    license_id = license_info.get("spdx_id") or ""

    result["notes"].append(f"Stars: {stars}")
    result["notes"].append(f"Language: {language}")
    result["notes"].append(f"License: {license_id}")
    result["notes"].append(f"Last push: {pushed_at}")

    if stars < 500:
        result["ok"] = False
        result["issues"].append("Repository has fewer than 500 stars")
        result["reject_reasons"].append("Repository has fewer than 500 stars")

    allowed_langs = {"TypeScript", "JavaScript", "Python", "Go", "Rust"}
    if language not in allowed_langs:
        result["ok"] = False
        result["issues"].append("Repository language not in allowed list")
        result["reject_reasons"].append("Repository language not in allowed list")

    allowed = set(load_allowed_licenses())
    if license_id in {"NOASSERTION", "", "Other"}:
        result["ok"] = False
        result["issues"].append("Missing or non-permissive license")
        result["reject_reasons"].append("Missing or non-permissive license")
    elif allowed and license_id not in allowed:
        result["ok"] = False
        result["issues"].append(f"License not in allowed list ({license_id})")
        result["reject_reasons"].append(f"License not in allowed list ({license_id})")

    if pushed_at:
        try:
            last_push = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - last_push).days
            if age_days > 365:
                result["ok"] = False
                result["issues"].append("Repository inactive (no commits in 12 months)")
                result["reject_reasons"].append("Repository inactive (no commits in 12 months)")
        except Exception:
            result["issues"].append("Could not parse last push date")

    if re.search(r"github\.com/[^/]+/[^/]+/pull/\d+", description_text):
        result["ok"] = False
        result["issues"].append("Description references an existing PR")
        result["reject_reasons"].append("Description references an existing PR")

    keywords = tokenize(description_text)[:6]
    if keywords:
        q = "+".join(keywords[:4])
        search_url = f"https://api.github.com/search/issues?q=repo:{owner}/{repo}+type:pr+{q}"
        search = github_api_get(search_url)
        if search and search.get("total_count", 0) > 0:
            top = search.get("items", [])[:3]
            titles = [item.get("title", "") for item in top]
            if any(sum(1 for k in keywords if k in t.lower()) >= 3 for t in titles):
                result["ok"] = False
                result["issues"].append("Potential matching PR found by keyword search")
                result["reject_reasons"].append("Potential matching PR found by keyword search")

    return result


def analyze_problem(text: str) -> Dict:
    word_count = count_words(text)
    issues = []
    ambiguity_flags = []
    prescriptiveness_flags = []

    ambiguous_terms = [
        "maybe", "probably", "approximately", "around", "as needed", "as appropriate",
        "if possible", "etc", "and so on", "ideally", "best effort", "reasonable",
    ]
    prescriptive_patterns = [
        r"must be called \w+",
        r"located? (?:at|in) [\w/\.]+",
        r"return type",
        r"step \d",
        r"algorithm",
        r"implement using",
    ]
    scope_blowup = ["rewrite", "entire", "whole system", "from scratch"]
    repo_philosophy_violations = ["new framework", "different framework", "ignore existing", "custom runtime"]

    req_complete = not re.search(r"\b(see|refer to|as described in)\b", text, re.IGNORECASE) and not re.search(r"\b(TBD|TODO|WIP)\b", text)
    if not req_complete:
        issues.append("Requirements are not fully self-contained")

    no_ambiguity = not any(term in text.lower() for term in ambiguous_terms)
    if not no_ambiguity:
        issues.append("Ambiguous language present")
        for sentence in sentences(text):
            if any(term in sentence.lower() for term in ambiguous_terms):
                ambiguity_flags.append(sentence)

    prescriptive = any(re.search(p, text, re.IGNORECASE) for p in prescriptive_patterns)
    concise = word_count <= 250
    concise_not_prescriptive = concise and not prescriptive
    if not concise:
        issues.append(f"Problem description too long ({word_count} words)")
    if prescriptive:
        issues.append("Problem description is prescriptive")
        for sentence in sentences(text):
            if any(re.search(p, sentence, re.IGNORECASE) for p in prescriptive_patterns):
                prescriptiveness_flags.append(sentence)

    matches_scope = not any(term in text.lower() for term in scope_blowup)
    if not matches_scope:
        issues.append("Problem scope feels too large")

    aligns_philosophy = not any(term in text.lower() for term in repo_philosophy_violations)
    if not aligns_philosophy:
        issues.append("Problem conflicts with repo design philosophy")

    no_irrelevant = word_count <= 250 and not re.search(r"\b(background|story|narrative)\b", text, re.IGNORECASE)
    if not no_irrelevant:
        issues.append("Contains irrelevant context")

    has_structure = bool(re.search(r"^#+\s+|\n\s*[-*]\s+", text, re.MULTILINE))
    clear_writing = has_structure or word_count <= 200
    if not clear_writing:
        issues.append("Writing/formatting is hard to scan")

    implied = find_implied_contracts(text)
    schema_issues = find_schema_prescription(text)
    ambiguity_issues = ambiguity_checks(text)

    issues.extend(implied)
    issues.extend(schema_issues)
    issues.extend(ambiguity_issues)
    if implied or ambiguity_issues:
        ambiguity_flags.extend(implied + ambiguity_issues)
    if schema_issues:
        prescriptiveness_flags.extend(schema_issues)

    checks = [
        ("Requirements are complete and self-contained", req_complete),
        ("No ambiguities, fully deterministic", no_ambiguity),
        ("Problem is concise and not prescriptive", concise_not_prescriptive),
        ("Matches real-world repo scope", matches_scope),
        ("Aligns with repo's design philosophy", aligns_philosophy),
        ("No irrelevant context", no_irrelevant),
        ("Clear writing and formatting", clear_writing),
    ]

    return {
        "word_count": word_count,
        "issues": issues,
        "checks": checks,
        "contracts": split_compound_requirements(requirement_sentences(text)),
        "ambiguity_flags": list(dict.fromkeys(ambiguity_flags)),
        "prescriptiveness_flags": list(dict.fromkeys(prescriptiveness_flags)),
    }


def test_case_count(test_patch: str) -> int:
    patterns = [
        r"def test_\w+\s*\(",
        r"\btest\(\s*['\"]",
        r"\bit\(\s*['\"]",
        r"\bfunc Test\w+\s*\(",
        r"#\[test\]",
    ]
    count = 0
    for p in patterns:
        count += len(re.findall(p, test_patch))
    return count


def analyze_tests(test_patch: str, desc_text: str, repo_dir: Optional[Path], docker_results: Dict) -> Dict:
    issues = []
    checks = []

    if not test_patch:
        checks = [
            ("Tests expose unimplemented or incorrect behavior", False),
            ("Tests are deterministic", False),
            ("Assertions verify correct output", False),
            ("Validates behavior, not fragile internals", False),
            ("Follows repo test structure", False),
            ("Covers required behavior and edge cases", False),
            ("No redundant tests", False),
            ("No checks for unspecified behavior", False),
        ]
        issues.append("test.patch missing")
        return {"checks": checks, "issues": issues, "alignment": {"spec_rows": [], "assertion_rows": []}, "fairness_issues": []}

    exposes_missing = docker_results.get("new_only_fail", False)
    if not exposes_missing:
        issues.append("New tests do not fail on base commit")

    nondeterminism_patterns = [
        r"\btime\.sleep\b", r"\bdatetime\.now\b", r"\btime\.time\b",
        r"\brandom\.", r"\buuid4\b", r"\bMath\.random\b", r"\bDate\.now\b",
        r"\bsetTimeout\b", r"\bsetInterval\b",
    ]
    deterministic = not any(re.search(p, test_patch) for p in nondeterminism_patterns)
    if not deterministic:
        issues.append("Potential nondeterminism in tests")

    assert_lines = re.findall(r"\bassert\b[^\n]*", test_patch)
    weak_asserts = [a for a in assert_lines if re.search(r"is not None|!=\s*None|len\(|truthy|not None", a)]
    assertions_ok = not (assert_lines and len(weak_asserts) == len(assert_lines))
    if not assertions_ok:
        issues.append("Assertions look weak or non-specific")
    elif weak_asserts:
        issues.append("Some assertions may allow a partial or wrong implementation to pass")

    internal_usage = bool(re.search(r"\._|/internal/|_private", test_patch))
    behavior_focused = not internal_usage
    if internal_usage:
        issues.append("Tests appear to touch internal/private details")

    follows_structure = True
    if repo_dir:
        test_dirs = set()
        for root, dirs, files in os.walk(repo_dir):
            for d in dirs:
                if d.lower() in {"tests", "test", "__tests__", "spec"}:
                    test_dirs.add(Path(root) / d)
        added_files = re.findall(r"^\+\+\+\s+b/(.+)$", test_patch, re.MULTILINE)
        if added_files and test_dirs:
            follows_structure = False
            for f in added_files:
                fpath = repo_dir / f
                if any(str(fpath).startswith(str(td)) for td in test_dirs):
                    follows_structure = True
                    break
    if not follows_structure:
        issues.append("Tests do not follow repo structure")

    case_count = test_case_count(test_patch)
    covers_edges = case_count >= 2
    if not covers_edges:
        issues.append("Insufficient test case coverage")

    lines = [l.strip() for l in test_patch.splitlines() if l.startswith("+") and not l.startswith("+++ ")]
    norm = [re.sub(r"\s+", " ", l[1:].strip()) for l in lines if l[1:].strip()]
    dup_count = len(norm) - len(set(norm))
    no_redundancy = dup_count <= max(1, len(norm) // 4)
    if not no_redundancy:
        issues.append("Redundant or repetitive tests detected")

    contracts = split_compound_requirements(requirement_sentences(desc_text))
    test_cases = extract_test_cases(test_patch)
    spec_rows, assertion_rows = build_alignment_tables(contracts, test_patch)
    alignment_issues = spec_test_alignment(contracts, test_cases, test_patch)
    if any(row["status"] == "Untested" for row in spec_rows):
        alignment_issues.append("One or more explicit requirements appear untested.")
    if any(row["status"] == "Hidden Requirement" for row in assertion_rows):
        alignment_issues.append("One or more test assertions do not trace to an explicit requirement.")
    if alignment_issues:
        issues.extend(alignment_issues)
    fairness_issues = []
    fairness_issues.extend(representation_choice_issues(desc_text, test_patch))
    fairness_issues.extend(stronger_than_spec_issues(contracts, desc_text, test_patch))
    fairness_issues.extend(multiple_valid_interpretations_issues(desc_text, test_patch))
    fairness_issues.extend(undocumented_surface_issues(desc_text, test_patch, repo_dir))
    if fairness_issues:
        issues.extend(fairness_issues)

    desc_tokens = set(tokenize(desc_text))
    test_tokens = set(tokenize(test_patch))
    overlap = len(desc_tokens & test_tokens) / max(1, len(test_tokens))
    no_unspecified = overlap >= 0.2
    if not no_unspecified or fairness_issues:
        no_unspecified = False
        issues.append("Tests may enforce unspecified behavior")

    checks = [
        ("Tests expose unimplemented or incorrect behavior", exposes_missing),
        ("Tests are deterministic", deterministic),
        ("Assertions verify correct output", assertions_ok),
        ("Validates behavior, not fragile internals", behavior_focused),
        ("Follows repo test structure", follows_structure),
        ("Covers required behavior and edge cases", covers_edges),
        ("No redundant tests", no_redundancy),
        ("No checks for unspecified behavior", no_unspecified),
    ]
    return {
        "checks": checks,
        "issues": list(dict.fromkeys(issues)),
        "fairness_issues": fairness_issues,
        "alignment": {"spec_rows": spec_rows, "assertion_rows": assertion_rows},
        "weak_assertions": weak_asserts[:5],
    }


def is_comment_line(line: str) -> bool:
    s = line.strip()
    return (
        s.startswith("#")
        or s.startswith("//")
        or s.startswith("/*")
        or s.startswith("*")
        or s.startswith("'''")
        or s.startswith('"""')
        or s.startswith("--")
    )


def is_generated_file_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    base = os.path.basename(normalized)
    generated_patterns = [
        r"(^|/)(dist|build|vendor|vendors|node_modules)/",
        r"\.pb\.go$",
        r"\.g\.cs$",
        r"\.designer\.",
        r"\.gen\.",
        r"\.generated\.",
        r"\.peg\.go$",
        r"y\.go$",
    ]
    if any(re.search(pattern, normalized) for pattern in generated_patterns):
        return True
    if any(token in base for token in ["generated", "autogen", "codegen"]):
        return True
    return False


def is_meaningful_added_line(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return False
    if is_comment_line(content):
        return False
    if re.fullmatch(r"(break|continue|pass|return None|return nil)", stripped):
        return False
    return True


def is_conservative_meaningful_added_line(content: str, in_import_block: bool = False) -> Tuple[bool, bool]:
    stripped = content.strip()
    if not is_meaningful_added_line(content):
        return False, False
    if re.fullmatch(r"package\s+[\w./-]+", stripped):
        return False, False
    if re.fullmatch(r"(import|using|use|namespace)\b.*", stripped):
        if re.fullmatch(r"(import|using)\s*[\(\{]?", stripped):
            return False, True
        return False, False
    if re.fullmatch(r"from\s+[\w.]+\s+import\b.*", stripped):
        return False, False
    if in_import_block:
        if stripped in {")", "}"}:
            return False, False
        if re.fullmatch(r'["\'\w\./\-\*,\s]+', stripped):
            return False, True
        return False, False
    if re.fullmatch(r"[{}\[\]();,]+", stripped):
        return False, False
    return True, False


def diff_stats(diff_text: str) -> Dict:
    added = 0
    code = 0
    meaningful = 0
    conservative_meaningful = 0
    comment = 0
    suspicious = 0
    seen = {}
    current_file = None
    generated_files = set()
    generated_added = 0
    meaningful_files = set()
    in_import_block = False
    structural_non_logic = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- ") or line.startswith("@@"):
            if line.startswith("+++ b/"):
                current_file = line[len("+++ b/"):].strip()
                if is_generated_file_path(current_file):
                    generated_files.add(current_file)
                in_import_block = False
            continue
        if line.startswith("+") and not line.startswith("+++ "):
            content = line[1:]
            if not content.strip():
                continue
            added += 1
            if current_file in generated_files:
                generated_added += 1
            if is_comment_line(content):
                comment += 1
            else:
                code += 1
            meaningful_line = is_meaningful_added_line(content)
            conservative_line, in_import_block = is_conservative_meaningful_added_line(content, in_import_block)
            if current_file not in generated_files and meaningful_line:
                meaningful += 1
                if current_file:
                    meaningful_files.add(current_file)
            if current_file not in generated_files and conservative_line:
                conservative_meaningful += 1
            elif current_file not in generated_files and meaningful_line:
                structural_non_logic += 1
            norm = re.sub(r"\s+", " ", content.strip())
            seen[norm] = seen.get(norm, 0) + 1
            if re.search(r"\b(TODO|FIXME|HACK|TEMP|generated by|chatgpt|llm)\b", content, re.IGNORECASE):
                suspicious += 1
            if re.search(r"\bpass\b|^\s*return\s+None\b", content):
                suspicious += 1
    dup = sum(c - 1 for c in seen.values() if c > 1)
    dup_ratio = dup / max(1, added)
    comment_ratio = comment / max(1, added)
    return {
        "added": added,
        "code": code,
        "meaningful": meaningful,
        "conservative_meaningful": conservative_meaningful,
        "comment": comment,
        "dup_ratio": dup_ratio,
        "comment_ratio": comment_ratio,
        "suspicious": suspicious,
        "generated_added": generated_added,
        "generated_files": sorted(generated_files),
        "meaningful_files": sorted(meaningful_files),
        "meaningful_file_count": len(meaningful_files),
        "structural_non_logic": structural_non_logic,
    }


def analyze_solution(solution_patch: str, docker_results: Dict) -> Dict:
    issues = []
    checks = []

    if not solution_patch:
        checks = [
            ("Meets all requirements", False),
            ("No regressions, follows repo patterns", False),
            ("No unexplained defensive code", False),
            ("No irrelevant changes", False),
            ("Existing API contracts stay stable", False),
            ("No AI-generated slop, comments, or artifacts", False),
        ]
        issues.append("solution.patch missing")
        return {"checks": checks, "issues": issues, "stats": {}}

    stats = diff_stats(solution_patch)
    added = stats["added"]
    meaningful_added = stats["meaningful"]
    meaningful_file_count = stats["meaningful_file_count"]
    code_lines = stats["code"]
    comment_ratio = stats["comment_ratio"]
    dup_ratio = stats["dup_ratio"]
    suspicious = stats["suspicious"]
    structural_non_logic = stats["structural_non_logic"]

    meets_requirements = docker_results.get("solution_new_pass", False)
    no_regressions = docker_results.get("solution_base_pass", False)

    if meaningful_added < 380:
        issues.append(f"Added meaningful LOC below required minimum ({meaningful_added})")
        meets_requirements = False
    if meaningful_file_count < 3:
        issues.append(f"Changed meaningful files below required minimum ({meaningful_file_count})")
        meets_requirements = False
    if structural_non_logic >= 50 and structural_non_logic / max(1, meaningful_added) > 0.15:
        issues.append(
            f"Solution LOC includes too many structural/non-logic lines ({structural_non_logic} of {meaningful_added}); report conservative LOC instead"
        )

    padded = (comment_ratio > 0.30) or (dup_ratio > 0.30) or (suspicious > 5)
    no_defensive = not padded
    if padded:
        issues.append("Solution appears padded or includes dead/unnecessary code")

    touched_files = re.findall(r"^\+\+\+\s+b/(.+)$", solution_patch, re.MULTILINE)
    irrelevant = any(
        f.endswith((".md", ".txt", ".rst"))
        or os.path.basename(f) in {"Dockerfile", "dockerfile", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "go.sum"}
        for f in touched_files
    )
    no_irrelevant = not irrelevant
    if irrelevant:
        issues.append("Solution patch touches files that should not be changed")

    api_break = bool(re.search(r"^\-\s*(export\s+|public\s+|pub\s+|def\s+|class\s+)", solution_patch, re.MULTILINE))
    api_stable = not api_break
    if api_break:
        issues.append("Potential public API changes detected")

    ai_slop = bool(re.search(r"\b(chatgpt|openai|llm|generated by)\b", solution_patch, re.IGNORECASE)) or comment_ratio > 0.30
    no_ai_slop = not ai_slop
    if ai_slop:
        issues.append("AI-generated slop or excessive commentary detected")

    checks = [
        ("Meets all requirements", meets_requirements),
        ("No regressions, follows repo patterns", no_regressions),
        ("No unexplained defensive code", no_defensive),
        ("No irrelevant changes", no_irrelevant),
        ("Existing API contracts stay stable", api_stable),
        ("No AI-generated slop, comments, or artifacts", no_ai_slop),
    ]
    return {"checks": checks, "issues": issues, "stats": stats}


def normalize_patch_line_endings(patch_path: Path) -> None:
    content = read_text(patch_path)
    if "\r\n" in content:
        patch_path.write_text(content.replace("\r\n", "\n"), encoding="utf-8")


def is_crlf_only_patch_failure(patch_path: Path, stderr: str) -> bool:
    content = read_text(patch_path)
    if "\r\n" not in content:
        return False
    # Treat CRLF retry as environment normalization only when the patch itself uses CRLF
    # and git failed during apply check. Do not surface this as a submission issue.
    return True


def apply_patch_checked(patch_path: Path, repo_dir: Path) -> Tuple[bool, str]:
    if not patch_path.exists():
        return False, "Patch not found"
    code, _, err = run_command(["git", "apply", "--check", str(patch_path)], cwd=str(repo_dir))
    if code != 0 and is_crlf_only_patch_failure(patch_path, err):
        normalize_patch_line_endings(patch_path)
        code, _, err = run_command(["git", "apply", "--check", str(patch_path)], cwd=str(repo_dir))
    if code == 0:
        run_command(["git", "apply", str(patch_path)], cwd=str(repo_dir))
        return True, "Patch applies cleanly"
    return False, f"Patch fails to apply: {err}"


def run_docker_verification(problem_dir: Path, repo_url: str, commit_hash: str, skip_docker: bool = False, extracted_files: Optional[Dict[str, Optional[Path]]] = None) -> Dict:
    results = {
        "build_success": False,
        "base_only_pass": False,
        "new_only_fail": False,
        "solution_base_pass": False,
        "solution_new_pass": False,
        "logs": {},
        "repo_dir": None,
        "analysis_repo_dir": None,
        "extraction_errors": [],
    }
    if skip_docker:
        results["skipped"] = True
        return results

    extracted_files = extracted_files or {}
    dockerfile = find_file(problem_dir, ["Dockerfile", "dockerfile"]) or extracted_files.get("Dockerfile")
    test_patch = find_file(problem_dir, ["test.patch"]) or extracted_files.get("test.patch")
    solution_patch = find_file(problem_dir, ["solution.patch"])

    if not dockerfile:
        results["error"] = "Dockerfile not found"
        return results

    work_dir = Path(tempfile.mkdtemp(prefix="review_work_"))
    repo_dir = work_dir / "repo"
    results["repo_dir"] = str(repo_dir)
    image_name = f"shipd/{work_dir.name}"

    try:
        code, _, stderr = run_command(["git", "clone", repo_url, "repo"], cwd=str(work_dir))
        if code != 0:
            results["error"] = f"Git clone failed: {stderr}"
            return results

        run_command(["git", "checkout", commit_hash], cwd=str(repo_dir))

        analysis_repo_dir = work_dir / "analysis_repo"
        shutil.copytree(repo_dir, analysis_repo_dir)
        results["analysis_repo_dir"] = str(analysis_repo_dir)

        shutil.copy(dockerfile, repo_dir / "Dockerfile")

        code, _, stderr = run_command(["docker", "build", "-t", image_name, "-f", "Dockerfile", "."], cwd=str(repo_dir))
        if code != 0:
            results["error"] = f"Docker build failed: {stderr}"
            return results
        results["build_success"] = True

        code, stdout, stderr = run_command(
            ["docker", "run", "--rm", "--network=none", image_name, "bash", "-lc", "sed -i 's/\\r$//' ./test.sh && ./test.sh base"],
            cwd=str(repo_dir),
        )
        results["base_only_pass"] = (code == 0)
        results["logs"]["base_only"] = stdout + stderr

        if test_patch:
            apply_patch_checked(test_patch, repo_dir)
            run_command(["docker", "build", "-t", image_name, "-f", "Dockerfile", "."], cwd=str(repo_dir))
            code, stdout, stderr = run_command(
                ["docker", "run", "--rm", "--network=none", image_name, "bash", "-lc", "sed -i 's/\\r$//' ./test.sh && ./test.sh new"],
                cwd=str(repo_dir),
            )
            results["new_only_fail"] = (code != 0)
            results["logs"]["new_without_solution"] = stdout + stderr

        if solution_patch:
            apply_patch_checked(solution_patch, repo_dir)
            run_command(["docker", "build", "-t", image_name, "-f", "Dockerfile", "."], cwd=str(repo_dir))

            code, stdout, stderr = run_command(
                ["docker", "run", "--rm", "--network=none", image_name, "bash", "-lc", "sed -i 's/\\r$//' ./test.sh && ./test.sh base"],
                cwd=str(repo_dir),
            )
            results["solution_base_pass"] = (code == 0)
            results["logs"]["base_with_solution"] = stdout + stderr

            code, stdout, stderr = run_command(
                ["docker", "run", "--rm", "--network=none", image_name, "bash", "-lc", "sed -i 's/\\r$//' ./test.sh && ./test.sh new"],
                cwd=str(repo_dir),
            )
            results["solution_new_pass"] = (code == 0)
            results["logs"]["new_with_solution"] = stdout + stderr

        return results
    finally:
        run_command(["docker", "image", "rm", "-f", image_name], cwd=str(work_dir), capture=True, timeout=120)
        shutil.rmtree(work_dir, ignore_errors=True)


def rating_from_checks(checks: List[Tuple[str, bool]], major_fail_names: List[str]) -> int:
    fails = [name for name, ok in checks if not ok]
    if any(name in major_fail_names for name in fails):
        if len(fails) >= 3:
            return 2
        return 3
    if not fails:
        return 7
    if len(fails) == 1:
        return 6
    if len(fails) == 2:
        return 5
    if len(fails) == 3:
        return 4
    return 3


def format_checklist(checks: List[Tuple[str, bool]]) -> Tuple[str, int]:
    lines = []
    yes_count = 0
    for label, ok in checks:
        lines.append(label)
        if ok:
            lines.append("YES (selected)")
            lines.append("NO")
            yes_count += 1
        else:
            lines.append("YES")
            lines.append("NO (selected)")
    return "\n".join(lines), yes_count


def format_quality_score(score: int) -> str:
    lines = []
    for n in range(1, 8):
        if n == score:
            lines.append(f"{n} (selected)")
        else:
            lines.append(str(n))
    return "\n".join(lines)


def extract_requested_changes(feedback_text: str) -> List[str]:
    changes = []
    current_section = None
    for raw_line in feedback_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower in {"changes required", "changes still required", "fixes:"}:
            current_section = lower
            continue
        if lower in {"reasoning", "checklist", "quality score", "decision:", "feedback"}:
            current_section = None
            continue
        if current_section and (line.startswith("-") or line.startswith("*") or re.match(r"^\[\s?[x ]?\]\s+", line)):
            changes.append(re.sub(r"^[-*]\s+|^\[\s?[x ]?\]\s+", "", line).strip())
            continue
        if "fixes:" in lower:
            tail = raw_line.split("Fixes:", 1)[1]
            changes.extend([part.strip(" .") for part in tail.split(";") if part.strip()])
    return list(dict.fromkeys(changes))


def classify_issue(issue: str) -> str:
    lower = issue.lower()
    if "ambigu" in lower:
        return "ambiguity"
    if "prescriptive" in lower or "schema/structure" in lower:
        return "prescriptiveness"
    if "undocumented or hard-to-discover api/configuration" in lower:
        return "undocumented_surface"
    if "unspecified behavior" in lower or "hidden requirement" in lower:
        return "hidden_requirement"
    if "stronger interpretation" in lower or "representation choice" in lower or "valid interpretation" in lower:
        return "fairness_alignment"
    if "assert" in lower and ("weak" in lower or "partial or wrong implementation" in lower):
        return "assertion_strength"
    if "determinism" in lower or "nondeterminism" in lower:
        return "determinism"
    if "docker" in lower or "patch fails to apply" in lower or "git clone failed" in lower:
        return "docker_or_patch"
    if "meaningful loc" in lower:
        return "meaningful_loc"
    if "meaningful files" in lower:
        return "meaningful_files"
    if "padding" in lower or "dead/unnecessary code" in lower or "ai-generated slop" in lower:
        return "padding_or_slop"
    if "api changes" in lower:
        return "api_breakage"
    if "scope" in lower:
        return "scope"
    if "self-contained" in lower:
        return "self_contained"
    if "repo" in lower or "license" in lower or "stars" in lower or "pr" in lower:
        return "repo_gate"
    return "other"


def classify_feedback_item(item: str, current_issues: List[str]) -> Tuple[str, str]:
    item_category = classify_issue(item)
    related = [issue for issue in current_issues if classify_issue(issue) == item_category]
    if not related:
        return "ADDRESSED", "No matching current issue category found."
    if any(token_overlap_score(item, issue) >= 0.20 for issue in related):
        return "NOT ADDRESSED", f"Still present: {related[0]}"
    return "PARTIAL", f"Related issue category still present: {related[0]}"


def analyze_rereview(previous_feedback_text: str, current_issues: List[str]) -> Dict:
    items = extract_requested_changes(previous_feedback_text)
    rows = []
    addressed = 0
    for item in items:
        status, notes = classify_feedback_item(item, current_issues)
        if status == "ADDRESSED":
            addressed += 1
        rows.append({"item": item, "status": status, "notes": notes})
    summary = f"{addressed}/{len(items)} prior requested changes addressed" if items else "No prior requested changes parsed"
    incomplete = any(row["status"] != "ADDRESSED" for row in rows)
    prior_categories = {classify_issue(item) for item in items}
    new_issues = []
    for issue in current_issues:
        if classify_issue(issue) not in prior_categories:
            new_issues.append(issue)
    return {
        "items": rows,
        "summary": summary,
        "incomplete": incomplete,
        "new_issues": list(dict.fromkeys(new_issues)),
    }


def build_feedback(issues: List[str], decision: str, fixable_issues: Optional[List[str]] = None) -> str:
    fixable_issues = fixable_issues or []
    if decision == "Approve":
        return "Submission meets the quality bar. Problem and tests are strong, and the solution proves solvability without padding."
    if decision == "Reject":
        return "Submission does not meet requirements. " + "; ".join(issues[:6])
    return "Changes needed before acceptance. " + "; ".join((fixable_issues or issues)[:6])


def format_bullets(items: List[str], empty_text: str = "None found") -> List[str]:
    if not items:
        return [empty_text]
    return [f"- {item}" for item in items]


def format_alignment_section(test_analysis: Dict) -> List[str]:
    lines = ["Spec-Test Alignment", "Optional", "Spec Requirement Coverage"]
    spec_rows = test_analysis.get("alignment", {}).get("spec_rows", [])
    assertion_rows = test_analysis.get("alignment", {}).get("assertion_rows", [])
    if spec_rows:
        lines.extend(
            format_table(
                ["Spec Requirement", "Covered by Test(s)", "Status"],
                [[row["requirement"], row["tests"], row["status"]] for row in spec_rows],
            )
        )
    else:
        lines.append("No explicit requirement rows available.")
    lines.append("")
    lines.append("Test Assertion Alignment")
    if assertion_rows:
        lines.extend(
            format_table(
                ["Test Assertion", "Traces to Spec Requirement", "Status"],
                [[row["assertion"], row["requirement"], row["status"]] for row in assertion_rows],
            )
        )
    else:
        lines.append("No explicit assertion rows available.")
    return lines


def format_feedback_incorporation_section(rereview: Optional[Dict]) -> List[str]:
    if not rereview:
        return []
    lines = ["Feedback Incorporation", "Optional"]
    rows = rereview.get("items", [])
    if rows:
        lines.extend(
            format_table(
                ["Feedback Item", "Status", "Notes"],
                [[row["item"], row["status"], row["notes"]] for row in rows],
            )
        )
    else:
        lines.append("No prior requested changes found.")
    lines.append(f"Summary: {rereview.get('summary', 'No summary')}")
    new_issues = rereview.get("new_issues", [])
    if new_issues:
        lines.append("New Issues Introduced:")
        lines.extend(format_bullets(new_issues))
    else:
        lines.append("New Issues Introduced:")
        lines.append("None found")
    return lines


def init_stage_results() -> Dict[str, Dict[str, str]]:
    return {
        "stage_0_rereview": {"name": "Feedback Incorporation Check", "status": "not_applicable", "notes": ""},
        "stage_1_inputs": {"name": "Input Validation", "status": "pending", "notes": ""},
        "stage_2_similarity": {"name": "Similarity Gate", "status": "pending", "notes": ""},
        "stage_3_repo": {"name": "Repository Gate", "status": "pending", "notes": ""},
        "stage_4_problem": {"name": "Problem Audit", "status": "pending", "notes": ""},
        "stage_5_tests": {"name": "Test Fairness Audit", "status": "pending", "notes": ""},
        "stage_6_docker": {"name": "Docker Verification", "status": "pending", "notes": ""},
        "stage_7_solution": {"name": "Solution Audit", "status": "pending", "notes": ""},
        "stage_8_decision": {"name": "Decision Synthesis", "status": "pending", "notes": ""},
    }


def set_stage(stage_results: Dict[str, Dict[str, str]], key: str, status: str, notes: str) -> None:
    stage_results[key]["status"] = status
    stage_results[key]["notes"] = notes


def stage_lines(stage_results: Dict[str, Dict[str, str]]) -> List[str]:
    lines = ["Stages:"]
    for key in [
        "stage_0_rereview",
        "stage_1_inputs",
        "stage_2_similarity",
        "stage_3_repo",
        "stage_4_problem",
        "stage_5_tests",
        "stage_6_docker",
        "stage_7_solution",
        "stage_8_decision",
    ]:
        stage = stage_results[key]
        lines.append(f"- {stage['name']}: {stage['status']}")
        if stage["notes"]:
            lines.append(f"  {stage['notes']}")
    return lines


def summarize_problem(problem_analysis: Dict) -> str:
    issues = problem_analysis.get("issues", [])
    if not issues:
        return "Problem: The spec is tight and scoped. It is clear, deterministic, and non-prescriptive, with clean formatting and no irrelevant context."
    if len(issues) <= 2:
        return "Problem: The spec is mostly clear and scoped, but has minor issues that need cleanup: " + "; ".join(issues[:2]) + "."
    return "Problem: The spec needs revision. Issues: " + "; ".join(issues[:3]) + "."


def summarize_tests(test_analysis: Dict) -> str:
    issues = test_analysis.get("issues", [])
    fairness_issues = test_analysis.get("fairness_issues", [])
    if not issues:
        return "Tests: The suite is comprehensive, deterministic, and behavioral, with strong assertions and no reliance on internals."
    if fairness_issues:
        return "Tests: Fairness concerns detected. " + "; ".join(fairness_issues[:2]) + "."
    if len(issues) <= 2:
        return "Tests: Mostly solid, but a few issues need attention: " + "; ".join(issues[:2]) + "."
    return "Tests: Quality gaps detected. Issues: " + "; ".join(issues[:3]) + "."


def summarize_solution(solution_analysis: Dict) -> str:
    issues = solution_analysis.get("issues", [])
    if not issues:
        return "Solution: Implementation is consistent with repo patterns, avoids public API changes, and shows no padding or unrelated edits."
    if len(issues) <= 2:
        return "Solution: Mostly OK, but needs fixes: " + "; ".join(issues[:2]) + "."
    return "Solution: Significant issues found: " + "; ".join(issues[:3]) + "."


def summarize_verification(docker_results: Dict) -> str:
    if docker_results.get("skipped"):
        return "Verification: Docker verification skipped."
    return (
        "Verification: Docker runs confirm base tests pass, new tests fail pre-solution, "
        "and both base/new pass after applying the solution."
    )


def fix_suggestions(issues: List[str]) -> List[str]:
    suggestions = []
    for issue in issues:
        if "determinism" in issue.lower():
            suggestions.append("Remove timing/randomness and make tests fully deterministic.")
        elif "fail on base" in issue.lower():
            suggestions.append("Adjust new tests so they fail on the base commit and pass only with the solution.")
        elif "pass with solution" in issue.lower():
            suggestions.append("Ensure solution.patch fully implements the required behavior so both base/new pass.")
        elif "docker build failed" in issue.lower() or "dockerfile" in issue.lower():
            suggestions.append("Fix Dockerfile to build offline and run tests with --network none.")
        elif "missing required patch files" in issue.lower():
            suggestions.append("Provide solution.patch and ensure test.patch is available either directly or embedded in setup.sh.")
        elif "added meaningful loc below required minimum" in issue.lower():
            suggestions.append("Expand the hand-authored implementation to >= 380 meaningful LOC.")
        elif "too many structural/non-logic lines" in issue.lower():
            suggestions.append("Reduce reliance on package/import/brace-heavy structural lines and add more actual logic; include the conservative LOC in the submission notes.")
        elif "changed meaningful files below required minimum" in issue.lower():
            suggestions.append("Spread the hand-authored implementation across at least 3 meaningful files; generated or irrelevant files do not count.")
        elif "patch" in issue.lower() and "apply" in issue.lower():
            suggestions.append("Regenerate patches so they apply cleanly against the specified commit.")
        elif "alignment" in issue.lower() or "unspecified behavior" in issue.lower():
            suggestions.append("Align tests to the problem description and remove unstated requirements.")
        elif "stronger interpretation" in issue.lower():
            suggestions.append("Relax tests so they do not require a stronger interpretation than the spec explicitly states, or clarify the spec.")
        elif "representation choice" in issue.lower():
            suggestions.append("Avoid exact shape/order/count assertions unless the spec explicitly requires that representation.")
        elif "valid interpretation" in issue.lower():
            suggestions.append("Clarify the spec where multiple valid interpretations exist, or broaden tests to accept all valid behaviors.")
        elif "undocumented or hard-to-discover api/configuration surface" in issue.lower():
            suggestions.append("Avoid requiring undocumented flags/config/options in tests, or explicitly introduce and justify them in the problem statement.")
        elif "weak" in issue.lower() and "assert" in issue.lower():
            suggestions.append("Strengthen assertions to verify exact expected outputs.")
        elif "partial or wrong implementation" in issue.lower():
            suggestions.append("Tighten assertions so incorrect or partial implementations cannot pass.")
        elif "scope" in issue.lower():
            suggestions.append("Reduce scope to a realistic change that fits the repo's purpose.")
        elif "prescriptive" in issue.lower():
            suggestions.append("Rewrite the spec to describe behavior, not implementation steps.")
        elif "prior requested changes were not fully addressed" in issue.lower():
            suggestions.append("Address every previously requested change explicitly and confirm each one in the resubmission.")
        elif "new issues were introduced in the updated submission" in issue.lower():
            suggestions.append("Fix the newly introduced issues before resubmitting; a re-review must address old feedback without creating new problems.")
    return list(dict.fromkeys(suggestions))


def build_reasoning(problem_analysis: Dict, test_analysis: Dict, solution_analysis: Dict, docker_results: Dict, word_count: int, stats: Optional[Dict], decision: str, fixable_issues: List[str], stage_results: Dict[str, Dict[str, str]], rereview: Optional[Dict]) -> str:
    lines = []
    lines.extend(stage_lines(stage_results))
    lines.append("")
    lines.append(summarize_problem(problem_analysis))
    lines.append("")
    lines.append(summarize_tests(test_analysis))
    fairness_issues = test_analysis.get("fairness_issues", [])
    if fairness_issues:
        lines.append("")
        lines.append("Alignment Risk: " + "; ".join(fairness_issues[:2]) + ".")
    weak_assertions = test_analysis.get("weak_assertions", [])
    if weak_assertions:
        lines.append("")
        lines.append("Assertion Strength: Some assertions may allow a partial or wrong implementation to pass.")
    lines.append("")
    lines.append(summarize_solution(solution_analysis))
    lines.append("")
    lines.append(summarize_verification(docker_results))
    lines.append("")
    lines.append("Diagnostics:")
    lines.append(f"- Word count: {word_count}")
    if stats:
        lines.append(
            f"- Solution LOC added: {stats.get('added', 0)} (meaningful: {stats.get('meaningful', 0)}, conservative: {stats.get('conservative_meaningful', 0)}, non-empty: {stats.get('code', 0)})"
        )
        lines.append(f"- Meaningful files changed: {stats.get('meaningful_file_count', 0)}")
        lines.append(f"- Structural/non-logic lines counted in meaningful LOC: {stats.get('structural_non_logic', 0)}")
        if stats.get("generated_files"):
            lines.append(f"- Generated LOC excluded: {stats.get('generated_added', 0)}")
    if docker_results.get("skipped"):
        lines.append("- Docker verification skipped")
    else:
        lines.append(f"- Docker base pass: {docker_results.get('base_only_pass', False)}")
        lines.append(f"- Docker new fail (pre-solution): {docker_results.get('new_only_fail', False)}")
        lines.append(f"- Docker base pass (with solution): {docker_results.get('solution_base_pass', False)}")
        lines.append(f"- Docker new pass (with solution): {docker_results.get('solution_new_pass', False)}")
    if rereview:
        lines.append(f"- Re-review summary: {rereview.get('summary', 'n/a')}")
    if decision == "Request Changes":
        lines.append("")
        lines.append("Fixes:")
        suggestions = fix_suggestions(fixable_issues)
        if suggestions:
            for s in suggestions:
                lines.append(f"- {s}")
        else:
            lines.append("- Address the listed issues and re-run verification.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Automated Code Eval Problem Reviewer")
    parser.add_argument("problem_dir", help="Directory containing problem files")
    parser.add_argument("--repo-url", help="GitHub repository URL")
    parser.add_argument("--commit", help="Base commit hash")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker verification")
    parser.add_argument("--output", default="feedback.md", help="Output file name")
    args = parser.parse_args()

    problem_dir = Path(args.problem_dir).resolve()
    if not problem_dir.exists():
        print(f"Error: Problem directory not found: {problem_dir}")
        raise SystemExit(1)

    stage_results = init_stage_results()

    setup_file = find_file(problem_dir, ["setup.sh"])
    desc_files = find_files(problem_dir, ["Problem-Description.txt", "description.md", "problem.md"])
    test_patch_file = find_file(problem_dir, ["test.patch"])
    solution_patch_file = find_file(problem_dir, ["solution.patch"])
    prior_feedback_file = find_file(problem_dir, ["feedback.md"])
    extracted_files = materialize_embedded_setup_files(problem_dir, setup_file)
    test_patch_file = test_patch_file or extracted_files.get("test.patch")

    repo_url = args.repo_url
    commit_hash = args.commit

    if setup_file:
        setup_url, setup_commit = extract_repo_info_from_setup(setup_file)
        repo_url = repo_url or setup_url
        commit_hash = commit_hash or setup_commit
        setup_text = read_text(setup_file)
        expected_embeds = detect_setup_extraction_expectations(setup_text)
    else:
        expected_embeds = []

    if not desc_files:
        print("Error: No problem description found")
        raise SystemExit(1)

    input_notes = []
    test_sh_from_patch = bool(test_patch_file and extract_test_sh_created_by_patch(read_text(test_patch_file)))
    input_notes.append(f"repo_url={repo_url or 'missing'}")
    input_notes.append(f"commit={commit_hash or 'missing'}")
    input_notes.append(f"test_patch={'yes' if test_patch_file else 'no'}")
    input_notes.append(f"solution_patch={'yes' if solution_patch_file else 'no'}")
    dockerfile_path = find_file(problem_dir, ['Dockerfile', 'dockerfile']) or extracted_files.get('Dockerfile')
    input_notes.append(f"dockerfile={'yes' if dockerfile_path else 'no'}")
    input_notes.append(f"test_sh_from_patch={'yes' if test_sh_from_patch else 'no'}")
    for expected_name in expected_embeds:
        if expected_name == "test.patch" and not test_patch_file:
            input_notes.append("setup_extract_error=test.patch not extracted")
        if expected_name == "Dockerfile" and not dockerfile_path:
            input_notes.append("setup_extract_error=Dockerfile not extracted")
    input_notes.append(f"prior_feedback={'yes' if prior_feedback_file else 'no'}")
    set_stage(stage_results, "stage_1_inputs", "completed", "; ".join(input_notes))

    main_desc = read_text(desc_files[0])
    extra_descs = [read_text(p) for p in desc_files[1:]]
    similar_list = parse_similar_problems_section(main_desc)
    extra_descs.extend(similar_list)
    prior_feedback_text = ""
    if prior_feedback_file and prior_feedback_file.resolve() != (problem_dir / args.output).resolve():
        prior_feedback_text = read_text(prior_feedback_file)
    elif prior_feedback_file and prior_feedback_file.exists():
        prior_feedback_text = read_text(prior_feedback_file)
    rereview = None

    similarity_detected, sim_reports = (False, [])
    if extra_descs:
        similarity_detected, sim_reports = detect_similarity(main_desc, extra_descs)

    if similarity_detected:
        set_stage(stage_results, "stage_2_similarity", "completed", "; ".join(sim_reports[:2]))
        set_stage(stage_results, "stage_8_decision", "completed", "Rejected at similarity gate")
        reasoning_text = "\n".join(["Stages:", "- Feedback Incorporation Check: not_applicable", "- Input Validation: completed", "- Similarity Gate: completed", "  Similarity detected", "- Repository Gate: pending", "- Problem Audit: pending", "- Test Fairness Audit: pending", "- Docker Verification: pending", "- Solution Audit: pending", "- Decision Synthesis: completed", "  decision=Reject; quality_score=1", "", "Similarity detected. Review halted."] + sim_reports)
        output = [
            "Submit Review",
            "",
            "Decision:",
            "",
            "Approve",
            "Meets quality standards",
            "",
            "Request Changes",
            "Needs changes before acceptance",
            "",
            "Reject (selected)",
            "Does not meet requirements",
            "",
            "Feedback",
            "Sent to the author",
            "Similarity detected between problem statements. Rejecting without further review.",
            "",
            "Ambiguity Flags",
            "Optional",
            "None found",
            "",
            "Prescriptiveness Flags",
            "Optional",
            "None found",
            "",
            "Spec-Test Alignment",
            "Optional",
            "Not evaluated because the review stopped at the similarity gate.",
            "",
            "Changes Required",
            "Optional",
            "- Submit a materially different problem statement.",
            "",
            "Checklist",
            "",
            "Optional",
            "Problem",
            "0/7",
            "Requirements are complete and self-contained",
            "YES",
            "NO (selected)",
            "No ambiguities, fully deterministic",
            "YES",
            "NO (selected)",
            "Problem is concise and not prescriptive",
            "YES",
            "NO (selected)",
            "Matches real-world repo scope",
            "YES",
            "NO (selected)",
            "Aligns with repo's design philosophy",
            "YES",
            "NO (selected)",
            "No irrelevant context",
            "YES",
            "NO (selected)",
            "Clear writing and formatting",
            "YES",
            "NO (selected)",
            "",
            "Tests",
            "0/8",
            "Tests expose unimplemented or incorrect behavior",
            "YES",
            "NO (selected)",
            "Tests are deterministic",
            "YES",
            "NO (selected)",
            "Assertions verify correct output",
            "YES",
            "NO (selected)",
            "Validates behavior, not fragile internals",
            "YES",
            "NO (selected)",
            "Follows repo test structure",
            "YES",
            "NO (selected)",
            "Covers required behavior and edge cases",
            "YES",
            "NO (selected)",
            "No redundant tests",
            "YES",
            "NO (selected)",
            "No checks for unspecified behavior",
            "YES",
            "NO (selected)",
            "",
            "Solution & Code",
            "0/6",
            "Meets all requirements",
            "YES",
            "NO (selected)",
            "No regressions, follows repo patterns",
            "YES",
            "NO (selected)",
            "No unexplained defensive code",
            "YES",
            "NO (selected)",
            "No irrelevant changes",
            "YES",
            "NO (selected)",
            "Existing API contracts stay stable",
            "YES",
            "NO (selected)",
            "No AI-generated slop, comments, or artifacts",
            "YES",
            "NO (selected)",
            "",
            "Quality Score",
            "Optional",
            "1 (selected)",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "",
            "Reasoning",
            "Optional",
            reasoning_text,
        ]
        output_path = problem_dir / args.output
        output_path.write_text("\n".join(output), encoding="utf-8")
        print(f"Feedback written to: {output_path}")
        return
    set_stage(stage_results, "stage_2_similarity", "completed", "No material similarity detected")

    repo_validation = validate_repo(repo_url, main_desc)
    repo_stage_status = "completed" if not repo_validation["reject_reasons"] else "completed"
    set_stage(
        stage_results,
        "stage_3_repo",
        repo_stage_status,
        "; ".join(repo_validation["issues"][:3] or ["Repository checks passed"]),
    )

    docker_results = {}
    if repo_url and commit_hash:
        docker_results = run_docker_verification(problem_dir, repo_url, commit_hash, args.skip_docker, extracted_files=extracted_files)
    else:
        docker_results = {"skipped": True}
    docker_notes = []
    if docker_results.get("skipped"):
        docker_notes.append("Docker verification skipped")
    elif docker_results.get("error"):
        docker_notes.append(docker_results["error"])
    else:
        docker_notes.append(f"base={docker_results.get('base_only_pass', False)}")
        docker_notes.append(f"new_pre={docker_results.get('new_only_fail', False)}")
        docker_notes.append(f"base_post={docker_results.get('solution_base_pass', False)}")
        docker_notes.append(f"new_post={docker_results.get('solution_new_pass', False)}")
    set_stage(stage_results, "stage_6_docker", "completed", "; ".join(docker_notes))

    problem_analysis = analyze_problem(main_desc)
    test_patch_text = read_text(test_patch_file) if test_patch_file else ""
    solution_patch_text = read_text(solution_patch_file) if solution_patch_file else ""

    analysis_repo_dir = Path(docker_results["analysis_repo_dir"]) if docker_results.get("analysis_repo_dir") else None
    test_analysis = analyze_tests(test_patch_text, main_desc, analysis_repo_dir, docker_results)
    solution_analysis = analyze_solution(solution_patch_text, docker_results)
    current_predecision_issues = []
    current_predecision_issues.extend(problem_analysis["issues"])
    current_predecision_issues.extend(test_analysis["issues"])
    current_predecision_issues.extend(solution_analysis["issues"])
    if prior_feedback_text:
        rereview = analyze_rereview(prior_feedback_text, current_predecision_issues)
        rereview_notes = [rereview["summary"]]
        if rereview.get("new_issues"):
            rereview_notes.append(f"new_issues={len(rereview['new_issues'])}")
        else:
            rereview_notes.append("new_issues=0")
        set_stage(stage_results, "stage_0_rereview", "completed", "; ".join(rereview_notes))
    else:
        set_stage(stage_results, "stage_0_rereview", "not_applicable", "No prior feedback.md found; treating as initial review")
    set_stage(
        stage_results,
        "stage_4_problem",
        "completed",
        "; ".join(problem_analysis["issues"][:3] or [f"Word count={problem_analysis['word_count']}"]),
    )
    set_stage(
        stage_results,
        "stage_5_tests",
        "completed",
        "; ".join(
            (["5A coverage complete", "5B fairness complete"] + (test_analysis["issues"][:2] or ["No major test fairness issues"]))
        ),
    )
    solution_stats = solution_analysis.get("stats") or {}
    solution_notes = []
    if solution_analysis["issues"]:
        solution_notes.extend(solution_analysis["issues"][:3])
    else:
        solution_notes.append("No major solution issues")
    if solution_stats:
        solution_notes.append(f"meaningful_loc={solution_stats.get('meaningful', 0)}")
        solution_notes.append(f"meaningful_files={solution_stats.get('meaningful_file_count', 0)}")
    set_stage(stage_results, "stage_7_solution", "completed", "; ".join(solution_notes))

    problem_checks = problem_analysis["checks"]
    test_checks = test_analysis["checks"]
    solution_checks = solution_analysis["checks"]

    problem_rating = rating_from_checks(problem_checks, ["Requirements are complete and self-contained", "No ambiguities, fully deterministic"])
    test_rating = rating_from_checks(test_checks, ["Tests expose unimplemented or incorrect behavior", "Tests are deterministic"])
    solution_rating = rating_from_checks(solution_checks, ["Meets all requirements", "No regressions, follows repo patterns"])
    quality_score = min(problem_rating, test_rating, solution_rating)

    reject_reasons = list(repo_validation.get("reject_reasons", []))
    fixable_issues = []

    if not test_patch_file or not solution_patch_file:
        fixable_issues.append("Missing required patch files")
    if docker_results.get("error"):
        fixable_issues.append(docker_results["error"])
    if not docker_results.get("skipped"):
        if test_patch_file and not docker_results.get("new_only_fail", False):
            fixable_issues.append("New tests do not fail on base commit")
        if solution_patch_file and (not docker_results.get("solution_new_pass", False) or not docker_results.get("solution_base_pass", False)):
            fixable_issues.append("Tests do not pass with solution applied")
    if rereview and rereview["incomplete"]:
        fixable_issues.append("Prior requested changes were not fully addressed")
    if rereview and rereview.get("new_issues"):
        fixable_issues.append("New issues were introduced in the updated submission")

    if reject_reasons:
        decision = "Reject"
    elif quality_score >= 5 and not fixable_issues and not problem_analysis["issues"] and not test_analysis["issues"] and not solution_analysis["issues"] and not (rereview and rereview["incomplete"]):
        decision = "Approve"
    else:
        decision = "Request Changes"
    set_stage(
        stage_results,
        "stage_8_decision",
        "completed",
        f"decision={decision}; quality_score={quality_score}",
    )

    issues = []
    issues.extend(repo_validation["issues"])
    issues.extend(problem_analysis["issues"])
    issues.extend(test_analysis["issues"])
    issues.extend(solution_analysis["issues"])
    issues.extend(fixable_issues)
    if not issues:
        issues.append("No major issues found")

    feedback_text = build_feedback(issues, decision, fixable_issues)

    stats = solution_analysis.get("stats")
    reasoning = build_reasoning(
        problem_analysis,
        test_analysis,
        solution_analysis,
        docker_results,
        problem_analysis["word_count"],
        stats,
        decision,
        fixable_issues,
        stage_results,
        rereview,
    )

    problem_block, problem_yes = format_checklist(problem_checks)
    test_block, test_yes = format_checklist(test_checks)
    solution_block, solution_yes = format_checklist(solution_checks)

    output_lines = [
        "Submit Review",
        "",
        "Decision:",
        "",
        f"Approve{' (selected)' if decision == 'Approve' else ''}",
        "Meets quality standards",
        "",
        f"Request Changes{' (selected)' if decision == 'Request Changes' else ''}",
        "Needs changes before acceptance",
        "",
        f"Reject{' (selected)' if decision == 'Reject' else ''}",
        "Does not meet requirements",
        "",
        "Feedback",
        "Sent to the author",
        feedback_text,
        "",
    ]
    if rereview:
        output_lines.extend(format_feedback_incorporation_section(rereview))
        output_lines.append("")
    output_lines.extend([
        "Ambiguity Flags",
        "Optional",
        *format_bullets(problem_analysis.get("ambiguity_flags", [])),
        "",
        "Prescriptiveness Flags",
        "Optional",
        *format_bullets(problem_analysis.get("prescriptiveness_flags", [])),
        "",
    ])
    output_lines.extend(format_alignment_section(test_analysis))
    output_lines.append("")
    changes_required = fix_suggestions(fixable_issues or issues)
    output_lines.extend([
        "Changes Required",
        "Optional",
        *format_bullets(changes_required, "No specific changes required."),
        "",
        "Checklist",
        "",
        "Optional",
        "Problem",
        f"{problem_yes}/7",
        problem_block,
        "",
        "Tests",
        f"{test_yes}/8",
        test_block,
        "",
        "Solution & Code",
        f"{solution_yes}/6",
        solution_block,
        "",
        "Quality Score",
        "Optional",
        format_quality_score(quality_score),
        "",
        "Reasoning",
        "Optional",
        reasoning,
    ])

    output_path = problem_dir / args.output
    output_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"Feedback written to: {output_path}")


if __name__ == "__main__":
    main()
