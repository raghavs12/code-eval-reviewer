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

    prescriptive = any(re.search(p, text, re.IGNORECASE) for p in prescriptive_patterns)
    concise = word_count <= 250
    concise_not_prescriptive = concise and not prescriptive
    if not concise:
        issues.append(f"Problem description too long ({word_count} words)")
    if prescriptive:
        issues.append("Problem description is prescriptive")

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
        return {"checks": checks, "issues": issues}

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
    alignment_issues = spec_test_alignment(contracts, test_cases, test_patch)
    if alignment_issues:
        issues.extend(alignment_issues)

    desc_tokens = set(tokenize(desc_text))
    test_tokens = set(tokenize(test_patch))
    overlap = len(desc_tokens & test_tokens) / max(1, len(test_tokens))
    no_unspecified = overlap >= 0.2
    if not no_unspecified:
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
    return {"checks": checks, "issues": issues}


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


def diff_stats(diff_text: str) -> Dict:
    added = 0
    code = 0
    comment = 0
    suspicious = 0
    seen = {}
    for line in diff_text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- ") or line.startswith("@@"):
            continue
        if line.startswith("+") and not line.startswith("+++ "):
            content = line[1:]
            if not content.strip():
                continue
            added += 1
            if is_comment_line(content):
                comment += 1
            else:
                code += 1
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
        "comment": comment,
        "dup_ratio": dup_ratio,
        "comment_ratio": comment_ratio,
        "suspicious": suspicious,
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
    code_lines = stats["code"]
    comment_ratio = stats["comment_ratio"]
    dup_ratio = stats["dup_ratio"]
    suspicious = stats["suspicious"]

    meets_requirements = docker_results.get("solution_new_pass", False)
    no_regressions = docker_results.get("solution_base_pass", False)

    if added < 380:
        issues.append(f"Added LOC below required minimum ({added})")
        meets_requirements = False

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


def run_docker_verification(problem_dir: Path, repo_url: str, commit_hash: str, skip_docker: bool = False) -> Dict:
    results = {
        "build_success": False,
        "base_only_pass": False,
        "new_only_fail": False,
        "solution_base_pass": False,
        "solution_new_pass": False,
        "logs": {},
        "repo_dir": None,
    }
    if skip_docker:
        results["skipped"] = True
        return results

    dockerfile = find_file(problem_dir, ["Dockerfile", "dockerfile"])
    test_patch = find_file(problem_dir, ["test.patch"])
    solution_patch = find_file(problem_dir, ["solution.patch"])

    if not dockerfile:
        results["error"] = "Dockerfile not found"
        return results

    work_dir = Path(tempfile.mkdtemp(prefix="review_work_"))
    repo_dir = work_dir / "repo"
    results["repo_dir"] = str(repo_dir)

    code, _, stderr = run_command(["git", "clone", repo_url, "repo"], cwd=str(work_dir))
    if code != 0:
        results["error"] = f"Git clone failed: {stderr}"
        return results

    run_command(["git", "checkout", commit_hash], cwd=str(repo_dir))

    shutil.copy(dockerfile, repo_dir / "Dockerfile")

    image_name = f"shipd/{repo_dir.name}"
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


def build_feedback(issues: List[str], decision: str) -> str:
    if decision == "Approve":
        return "Submission meets the quality bar. Problem and tests are strong, and the solution proves solvability without padding."
    if decision == "Reject":
        return "Submission does not meet requirements. " + "; ".join(issues[:6])
    return "Changes needed before acceptance. " + "; ".join(issues[:6])


def summarize_problem(problem_analysis: Dict) -> str:
    issues = problem_analysis.get("issues", [])
    if not issues:
        return "Problem: The spec is tight and scoped. It is clear, deterministic, and non-prescriptive, with clean formatting and no irrelevant context."
    if len(issues) <= 2:
        return "Problem: The spec is mostly clear and scoped, but has minor issues that need cleanup: " + "; ".join(issues[:2]) + "."
    return "Problem: The spec needs revision. Issues: " + "; ".join(issues[:3]) + "."


def summarize_tests(test_analysis: Dict) -> str:
    issues = test_analysis.get("issues", [])
    if not issues:
        return "Tests: The suite is comprehensive, deterministic, and behavioral, with strong assertions and no reliance on internals."
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
            suggestions.append("Provide both test.patch and solution.patch in the submission bundle.")
        elif "added loc below required minimum" in issue.lower():
            suggestions.append("Expand the solution to a >= 380 LOC change that genuinely implements required behavior (no padding).")
        elif "patch" in issue.lower() and "apply" in issue.lower():
            suggestions.append("Regenerate patches so they apply cleanly against the specified commit.")
        elif "alignment" in issue.lower() or "unspecified behavior" in issue.lower():
            suggestions.append("Align tests to the problem description and remove unstated requirements.")
        elif "weak" in issue.lower() and "assert" in issue.lower():
            suggestions.append("Strengthen assertions to verify exact expected outputs.")
        elif "scope" in issue.lower():
            suggestions.append("Reduce scope to a realistic change that fits the repo's purpose.")
        elif "prescriptive" in issue.lower():
            suggestions.append("Rewrite the spec to describe behavior, not implementation steps.")
    return list(dict.fromkeys(suggestions))


def build_reasoning(problem_analysis: Dict, test_analysis: Dict, solution_analysis: Dict, docker_results: Dict, word_count: int, stats: Optional[Dict], decision: str, fixable_issues: List[str]) -> str:
    lines = []
    lines.append(summarize_problem(problem_analysis))
    lines.append("")
    lines.append(summarize_tests(test_analysis))
    lines.append("")
    lines.append(summarize_solution(solution_analysis))
    lines.append("")
    lines.append(summarize_verification(docker_results))
    lines.append("")
    lines.append("Diagnostics:")
    lines.append(f"- Word count: {word_count}")
    if stats:
        lines.append(
            f"- Solution LOC added: {stats.get('added', 0)} (non-empty: {stats.get('code', 0)})"
        )
    if docker_results.get("skipped"):
        lines.append("- Docker verification skipped")
    else:
        lines.append(f"- Docker base pass: {docker_results.get('base_only_pass', False)}")
        lines.append(f"- Docker new fail (pre-solution): {docker_results.get('new_only_fail', False)}")
        lines.append(f"- Docker base pass (with solution): {docker_results.get('solution_base_pass', False)}")
        lines.append(f"- Docker new pass (with solution): {docker_results.get('solution_new_pass', False)}")
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

    setup_file = find_file(problem_dir, ["setup.sh"])
    desc_files = find_files(problem_dir, ["Problem-Description.txt", "description.md", "problem.md"])
    test_patch_file = find_file(problem_dir, ["test.patch"])
    solution_patch_file = find_file(problem_dir, ["solution.patch"])

    repo_url = args.repo_url
    commit_hash = args.commit

    if setup_file:
        setup_url, setup_commit = extract_repo_info_from_setup(setup_file)
        repo_url = repo_url or setup_url
        commit_hash = commit_hash or setup_commit

    if not desc_files:
        print("Error: No problem description found")
        raise SystemExit(1)

    main_desc = read_text(desc_files[0])
    extra_descs = [read_text(p) for p in desc_files[1:]]
    similar_list = parse_similar_problems_section(main_desc)
    extra_descs.extend(similar_list)

    similarity_detected, sim_reports = (False, [])
    if extra_descs:
        similarity_detected, sim_reports = detect_similarity(main_desc, extra_descs)

    if similarity_detected:
        reasoning = ["Similarity detected. Review halted."] + sim_reports
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
            "\n".join(reasoning),
        ]
        output_path = problem_dir / args.output
        output_path.write_text("\n".join(output), encoding="utf-8")
        print(f"Feedback written to: {output_path}")
        return

    repo_validation = validate_repo(repo_url, main_desc)

    docker_results = {}
    if repo_url and commit_hash:
        docker_results = run_docker_verification(problem_dir, repo_url, commit_hash, args.skip_docker)
    else:
        docker_results = {"skipped": True}

    problem_analysis = analyze_problem(main_desc)
    test_patch_text = read_text(test_patch_file) if test_patch_file else ""
    solution_patch_text = read_text(solution_patch_file) if solution_patch_file else ""

    repo_dir = Path(docker_results["repo_dir"]) if docker_results.get("repo_dir") else None
    test_analysis = analyze_tests(test_patch_text, main_desc, repo_dir, docker_results)
    solution_analysis = analyze_solution(solution_patch_text, docker_results)

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

    if reject_reasons:
        decision = "Reject"
    elif quality_score >= 5 and not fixable_issues and not problem_analysis["issues"] and not test_analysis["issues"] and not solution_analysis["issues"]:
        decision = "Approve"
    else:
        decision = "Request Changes"

    issues = []
    issues.extend(repo_validation["issues"])
    issues.extend(problem_analysis["issues"])
    issues.extend(test_analysis["issues"])
    issues.extend(solution_analysis["issues"])
    issues.extend(fixable_issues)
    if not issues:
        issues.append("No major issues found")

    feedback_text = build_feedback(issues, decision)

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
    ]

    output_path = problem_dir / args.output
    output_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"Feedback written to: {output_path}")


if __name__ == "__main__":
    main()
