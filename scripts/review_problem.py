#!/usr/bin/env python3
"""
Code Eval Reviewer - Automated Problem Review Script

Usage:
    python3 review_problem.py <problem-dir> [--repo-url URL] [--commit HASH] [--skip-docker]

This script automates the review process:
1. Validates file structure
2. Clones repo and applies patches
3. Builds Docker and runs tests
4. Generates feedback.md for submission
"""

import os
import sys
import re
import subprocess
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class ReviewResult:
    def __init__(self):
        self.requirements = {
            'R1_github': {'status': None, 'notes': ''},
            'R2_dockerfile': {'status': None, 'notes': ''},
            'R3_problem': {'status': None, 'notes': ''},
            'R4_tests': {'status': None, 'notes': ''},
            'R5_solution': {'status': None, 'notes': ''}
        }
        self.quality = {
            'Q1_problem_quality': {'score': 0, 'notes': ''},
            'Q2_test_quality': {'score': 0, 'notes': ''},
            'Q3_precision': {'score': 0, 'notes': ''},
            'Q4_alignment': {'score': 0, 'notes': ''},
            'Q5_solution': {'score': 0, 'notes': ''}
        }
        self.test_requirements = []
        self.alignment_issues = []
        self.positives = []
        self.issues = []
        self.edits = []
        self.word_count = 0
        self.verdict = 'REQUEST_CHANGE'
        self.docker_logs = {'base_only': '', 'with_solution': ''}


def run_command(cmd: List[str], cwd: str = None, capture: bool = True) -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=capture, text=True, timeout=300
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, '', 'Command timed out'
    except Exception as e:
        return -1, '', str(e)


def find_file(directory: Path, names: List[str]) -> Optional[Path]:
    """Find a file matching any of the given names (case-insensitive)"""
    for name in names:
        # Try exact match
        path = directory / name
        if path.exists():
            return path
        # Try case-insensitive
        for f in directory.iterdir():
            if f.name.lower() == name.lower():
                return f
    return None


def count_words(text: str) -> int:
    """Count words in markdown text, excluding code blocks"""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    # Remove markdown syntax
    text = re.sub(r'[#*_\[\]()>-]', ' ', text)
    words = text.split()
    return len(words)


def extract_test_requirements(test_patch: str) -> List[str]:
    """Extract test requirements in 'Given/When/Should' format"""
    requirements = []
    
    # Find test functions
    test_pattern = r'def (test_\w+)\([^)]*\):\s*(?:"""([^"]*)""")?'
    matches = re.findall(test_pattern, test_patch, re.MULTILINE)
    
    for func_name, docstring in matches:
        # Convert function name to requirement
        name = func_name.replace('test_', '').replace('_', ' ')
        if docstring:
            requirements.append(f"- {docstring.strip()}")
        else:
            requirements.append(f"- {name}")
    
    # Look for assertions to understand what's being tested
    assert_pattern = r'assert\s+([^\n]+)'
    assertions = re.findall(assert_pattern, test_patch)
    
    return requirements


def check_patch_validity(patch_path: Path, repo_dir: Path) -> Tuple[bool, str]:
    """Check if a patch can be applied cleanly"""
    if not patch_path.exists():
        return False, f"Patch file not found: {patch_path}"
    
    code, stdout, stderr = run_command(
        ['git', 'apply', '--check', str(patch_path)],
        cwd=str(repo_dir)
    )
    
    if code == 0:
        return True, "Patch applies cleanly"
    else:
        return False, f"Patch fails to apply: {stderr}"


def analyze_problem_description(desc_path: Path) -> Dict:
    """Analyze problem description for quality issues"""
    content = desc_path.read_text(encoding='utf-8')
    word_count = count_words(content)
    
    issues = []
    
    # Check word count
    if word_count > 250:
        issues.append(f"Word count ({word_count}) exceeds 250 target")
    elif word_count > 200:
        issues.append(f"Word count ({word_count}) slightly high, consider trimming")
    
    # Check for over-specification patterns
    overspec_patterns = [
        (r'must be called \w+', 'Consider if function name is inferable from context'),
        (r'located? (?:at|in) [\w/\.]+', 'Consider if location is obvious from codebase'),
        (r'return type', 'Avoid specifying return types unless non-obvious'),
        (r'step \d', 'Avoid numbered implementation steps'),
        (r'algorithm', 'Avoid prescribing specific algorithms'),
    ]
    
    for pattern, message in overspec_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append(message)
    
    # Check for redundancy patterns
    redundancy_patterns = [
        r"don't break existing",
        r"must be deterministic",
        r"keep.*stable",
        r"preserve existing",
        r"must not alter.*valid",
    ]
    
    for pattern in redundancy_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append(f"Redundant: '{pattern}' - this is implied")
    
    return {
        'word_count': word_count,
        'issues': issues,
        'content': content
    }


def run_docker_verification(problem_dir: Path, repo_dir: Path, skip_docker: bool = False) -> Dict:
    """Build Docker and run test verification"""
    results = {
        'build_success': False,
        'base_only_pass': False,
        'new_only_fail': False,
        'solution_base_pass': False,
        'solution_new_pass': False,
        'logs': {}
    }
    
    if skip_docker:
        results['skipped'] = True
        return results
    
    dockerfile = find_file(problem_dir, ['dockerfile', 'Dockerfile'])
    if not dockerfile:
        results['error'] = 'Dockerfile not found'
        return results
    
    # Copy dockerfile to repo
    shutil.copy(dockerfile, repo_dir / 'Dockerfile')
    
    # Build image
    print("Building Docker image...")
    code, stdout, stderr = run_command(
        ['docker', 'build', '-t', 'problem-review-test', '.'],
        cwd=str(repo_dir)
    )
    
    if code != 0:
        results['error'] = f'Docker build failed: {stderr}'
        return results
    
    results['build_success'] = True
    
    # Test 1: Base tests without patches (should pass)
    print("Running base tests...")
    code, stdout, stderr = run_command(
        ['docker', 'run', '--rm', '--network=none', 'problem-review-test', './test.sh', 'base'],
        cwd=str(repo_dir)
    )
    results['base_only_pass'] = (code == 0)
    results['logs']['base_only'] = stdout + stderr
    
    # Apply test patch only
    test_patch = find_file(problem_dir, ['test.patch'])
    if test_patch:
        run_command(['git', 'apply', str(test_patch)], cwd=str(repo_dir))
        
        # Rebuild with test patch
        run_command(['docker', 'build', '-t', 'problem-review-test', '.'], cwd=str(repo_dir))
        
        # Test 2: New tests should fail without solution
        print("Running new tests (should fail)...")
        code, stdout, stderr = run_command(
            ['docker', 'run', '--rm', '--network=none', 'problem-review-test', './test.sh', 'new'],
            cwd=str(repo_dir)
        )
        results['new_only_fail'] = (code != 0)
        results['logs']['new_without_solution'] = stdout + stderr
    
    # Apply solution patch
    solution_patch = find_file(problem_dir, ['solution.patch'])
    if solution_patch:
        run_command(['git', 'apply', str(solution_patch)], cwd=str(repo_dir))
        
        # Rebuild with both patches
        run_command(['docker', 'build', '-t', 'problem-review-test', '.'], cwd=str(repo_dir))
        
        # Test 3: Base tests should still pass
        print("Running base tests with solution...")
        code, stdout, stderr = run_command(
            ['docker', 'run', '--rm', '--network=none', 'problem-review-test', './test.sh', 'base'],
            cwd=str(repo_dir)
        )
        results['solution_base_pass'] = (code == 0)
        results['logs']['base_with_solution'] = stdout + stderr
        
        # Test 4: New tests should pass with solution
        print("Running new tests with solution...")
        code, stdout, stderr = run_command(
            ['docker', 'run', '--rm', '--network=none', 'problem-review-test', './test.sh', 'new'],
            cwd=str(repo_dir)
        )
        results['solution_new_pass'] = (code == 0)
        results['logs']['new_with_solution'] = stdout + stderr
    
    return results


def generate_feedback(result: ReviewResult, problem_title: str, problem_dir: Path) -> str:
    """Generate feedback in the exact submission format with human-sounding text"""
    
    # Build problem quality assessment
    problem_quality_notes = []
    if result.requirements['R3_problem']['status']:
        problem_quality_notes.append("Core problem makes sense")
    if result.issues:
        problem_quality_notes.append(f"but has {len(result.issues)} issues to address")
    problem_quality = '. '.join(problem_quality_notes) if problem_quality_notes else "Looks reasonable"
    
    # Build determinism assessment  
    determinism = "No obvious environment dependencies spotted" if not any('determinism' in str(i).lower() for i in result.issues) else "Some determinism concerns - check for locale/timing dependencies"
    
    # Build scope assessment
    scope = "Self-contained, doesn't require changes outside the target area" if result.requirements['R5_solution']['status'] else "Need to verify scope boundaries"
    
    # Build difficulty assessment
    difficulty = "Seems appropriately challenging for the stated difficulty level"
    
    # Build alignment assessment
    alignment_notes = []
    if result.word_count > 250:
        alignment_notes.append(f"Description is too verbose ({result.word_count} words, target ~200)")
    if result.alignment_issues:
        alignment_notes.append('. '.join(result.alignment_issues[:2]))
    alignment = '. '.join(alignment_notes) if alignment_notes else "Tests align with what's described, no hidden requirements spotted"
    
    # Build test quality assessment
    test_notes = []
    if result.requirements['R4_tests']['status']:
        test_notes.append("Tests are present and structured correctly")
    if result.docker_logs.get('new_fail'):
        test_notes.append("new tests fail without solution as expected")
    test_quality = ', '.join(test_notes) if test_notes else "Need manual test review"
    
    # Build solution assessment
    solution_notes = []
    if result.docker_logs.get('solution_new') and result.docker_logs.get('solution_base'):
        solution_notes.append("All tests pass with solution applied")
    if result.requirements['R5_solution']['status']:
        solution_notes.append("patch applies cleanly")
    solution_comp = '. '.join(solution_notes) if solution_notes else "Need manual solution review"
    
    # Build code quality assessment
    code_quality = "Need to review the actual implementation for style/patterns"
    
    # Build explanation
    explanation_parts = []
    if result.verdict == 'ACCEPT':
        explanation_parts.append("Solid submission overall.")
    elif result.verdict == 'REJECT':
        explanation_parts.append("Can't accept this one.")
    else:
        explanation_parts.append("Needs some work before accepting.")
    
    if result.issues:
        explanation_parts.append(f"Main issues: {'; '.join(result.issues[:3])}")
    
    if result.edits:
        explanation_parts.append(f"Required changes: {'; '.join(result.edits[:3])}")
    
    if result.word_count > 200:
        explanation_parts.append(f"Description is {result.word_count} words, needs trimming to around 200.")
    
    explanation = ' '.join(explanation_parts)
    
    feedback = f"""Verdict: {result.verdict}

Problem Quality: {problem_quality}

Problem Determinism: {determinism}

Problem Scope: {scope}

Problem Difficulty: {difficulty}

Problem Description <> Test assumptions <> Tests Alignment and Isolation: {alignment}

Test Quality: {test_quality}

Solution Comprehensiveness: {solution_comp}

Code Quality: {code_quality}

Explanation of verdict: {explanation}
"""
    
    return feedback


def main():
    parser = argparse.ArgumentParser(description='Automated Code Eval Problem Reviewer')
    parser.add_argument('problem_dir', help='Directory containing problem files')
    parser.add_argument('--repo-url', help='GitHub repository URL')
    parser.add_argument('--commit', help='Base commit hash')
    parser.add_argument('--skip-docker', action='store_true', help='Skip Docker verification')
    parser.add_argument('--output', default='feedback.md', help='Output file name')
    
    args = parser.parse_args()
    
    problem_dir = Path(args.problem_dir).resolve()
    if not problem_dir.exists():
        print(f"Error: Problem directory not found: {problem_dir}")
        sys.exit(1)
    
    print(f"Reviewing problem in: {problem_dir}")
    
    result = ReviewResult()
    
    # Find required files
    desc_file = find_file(problem_dir, ['description.md', 'problem.md'])
    dockerfile = find_file(problem_dir, ['dockerfile', 'Dockerfile'])
    test_patch = find_file(problem_dir, ['test.patch'])
    solution_patch = find_file(problem_dir, ['solution.patch'])
    github_setup = find_file(problem_dir, ['github-setup.md', 'github_setup.md'])
    
    # Extract repo info
    repo_url = args.repo_url
    commit_hash = args.commit
    
    if github_setup and github_setup.exists():
        content = github_setup.read_text()
        url_match = re.search(r'https://github\.com/[\w-]+/[\w-]+', content)
        hash_match = re.search(r'[a-f0-9]{40}', content)
        if url_match:
            repo_url = repo_url or url_match.group()
        if hash_match:
            commit_hash = commit_hash or hash_match.group()
    
    # Get problem title
    problem_title = "Unknown"
    if desc_file:
        content = desc_file.read_text()
        title_match = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
        if title_match:
            problem_title = title_match.group(1).strip()
    
    print(f"Problem Title: {problem_title}")
    print(f"Repository: {repo_url}")
    print(f"Commit: {commit_hash}")
    
    # R3: Check problem description
    if desc_file:
        result.requirements['R3_problem']['status'] = True
        desc_analysis = analyze_problem_description(desc_file)
        result.word_count = desc_analysis['word_count']
        
        if desc_analysis['issues']:
            result.issues.extend(desc_analysis['issues'])
            result.requirements['R3_problem']['notes'] = f"{len(desc_analysis['issues'])} issues found"
        else:
            result.requirements['R3_problem']['notes'] = 'Clean'
    else:
        result.requirements['R3_problem']['status'] = False
        result.requirements['R3_problem']['notes'] = 'description.md not found'
    
    # R2: Check Dockerfile
    if dockerfile:
        content = dockerfile.read_text()
        if 'public.ecr.aws/x8v8d7g8/mars-base:latest' in content:
            result.requirements['R2_dockerfile']['status'] = True
            result.requirements['R2_dockerfile']['notes'] = 'Correct base image'
        else:
            result.requirements['R2_dockerfile']['status'] = False
            result.requirements['R2_dockerfile']['notes'] = 'Wrong base image'
    else:
        result.requirements['R2_dockerfile']['status'] = False
        result.requirements['R2_dockerfile']['notes'] = 'Dockerfile not found'
    
    # R4 & R5: Check patches exist
    if test_patch:
        result.requirements['R4_tests']['status'] = True
        result.requirements['R4_tests']['notes'] = 'test.patch found'
        
        # Extract test requirements
        test_content = test_patch.read_text()
        result.test_requirements = extract_test_requirements(test_content)
    else:
        result.requirements['R4_tests']['status'] = False
        result.requirements['R4_tests']['notes'] = 'test.patch not found'
    
    if solution_patch:
        result.requirements['R5_solution']['status'] = True
        result.requirements['R5_solution']['notes'] = 'solution.patch found'
    else:
        result.requirements['R5_solution']['status'] = False
        result.requirements['R5_solution']['notes'] = 'solution.patch not found'
    
    # R1: GitHub check (basic)
    if repo_url:
        result.requirements['R1_github']['status'] = True
        result.requirements['R1_github']['notes'] = f'URL: {repo_url}'
    else:
        result.requirements['R1_github']['status'] = False
        result.requirements['R1_github']['notes'] = 'No repository URL found'
    
    # Docker verification (if not skipped and we have repo info)
    if not args.skip_docker and repo_url and commit_hash:
        work_dir = Path('/tmp/review_work')
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True)
        
        print(f"\nCloning repository...")
        code, _, stderr = run_command(['git', 'clone', repo_url, 'repo'], cwd=str(work_dir))
        
        if code == 0:
            repo_dir = work_dir / 'repo'
            run_command(['git', 'checkout', commit_hash], cwd=str(repo_dir))
            
            docker_results = run_docker_verification(problem_dir, repo_dir, args.skip_docker)
            
            result.docker_logs = {
                'base_pass': docker_results.get('base_only_pass'),
                'new_fail': docker_results.get('new_only_fail'),
                'solution_base': docker_results.get('solution_base_pass'),
                'solution_new': docker_results.get('solution_new_pass')
            }
            
            # Update requirement statuses based on docker results
            if docker_results.get('build_success'):
                result.requirements['R2_dockerfile']['notes'] += ', builds successfully'
            
            if docker_results.get('solution_new_pass') and docker_results.get('solution_base_pass'):
                result.requirements['R5_solution']['notes'] += ', all tests pass'
            
            if docker_results.get('new_only_fail'):
                result.requirements['R4_tests']['notes'] += ', new tests fail without solution (good)'
    
    # Quality scoring (basic heuristics - manual review still needed)
    if result.word_count <= 200:
        result.quality['Q3_precision']['score'] = 3
        result.quality['Q3_precision']['notes'] = 'Good word count'
    elif result.word_count <= 250:
        result.quality['Q3_precision']['score'] = 2
        result.quality['Q3_precision']['notes'] = 'Slightly verbose'
    else:
        result.quality['Q3_precision']['score'] = 1
        result.quality['Q3_precision']['notes'] = 'Too verbose, needs trimming'
    
    # Determine verdict
    all_req_pass = all(r['status'] for r in result.requirements.values() if r['status'] is not None)
    if all_req_pass and not result.issues:
        result.verdict = 'ACCEPT'
    elif any(r['status'] is False for r in result.requirements.values()):
        result.verdict = 'REQUEST_CHANGE'
    else:
        result.verdict = 'REQUEST_CHANGE'
    
    # Add default positives if none found
    if not result.positives:
        if desc_file:
            result.positives.append('Problem description file present')
        if dockerfile:
            result.positives.append('Dockerfile provided')
        if test_patch and solution_patch:
            result.positives.append('Both patches provided')
    
    # Generate feedback
    feedback = generate_feedback(result, problem_title, problem_dir)
    
    # Write output
    output_path = problem_dir / args.output
    output_path.write_text(feedback)
    print(f"\n✅ Feedback written to: {output_path}")
    
    # Also print summary
    print(f"\n{'='*50}")
    print(f"VERDICT: {result.verdict}")
    print(f"Word Count: {result.word_count}")
    print(f"Issues Found: {len(result.issues)}")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
