#!/usr/bin/env python3
"""
Test and report script:
  - If a path argument is provided:
      * Validate the path exists, else log error and exit
      * Search recursively under that path for test projects (.csproj)
      * Store TestResults and coverage-report directories under the provided path
  - If no path argument is provided:
      * Look for a 'tests' folder directly under the current working directory
      * If not found: log error and exit
      * Search recursively under the 'tests' folder for test projects (.csproj)
      * Store TestResults under the 'tests' folder and coverage-report under a 'docs/coverage-report' folder (create docs/ if missing)
  - Ignore any test project whose path contains a directory named Setup (case-insensitive)
  - Run dotnet test with XPlat Code Coverage (json, lcov, cobertura)
  - Generate HTML coverage report using reportgenerator
"""
from __future__ import annotations
import sys, pathlib, shutil, subprocess, argparse


def log(msg: str):
    print(msg)


def error(msg: str):
    log(f"[ERROR] {msg}")
    sys.exit(1)


def ensure_dir(path: pathlib.Path):
    path.mkdir(parents=True, exist_ok=True)


def clean_dir(path: pathlib.Path):
    if path.exists():
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except Exception:
                    pass


def run(cmd: list[str]):
    log(f"[INFO] Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        log("[OK] Command finished successfully")
    except subprocess.CalledProcessError as e:
        error(f"Command failed with exit code {e.returncode}: {' '.join(cmd)}")


def is_setup_path(path: pathlib.Path) -> bool:
    # path parts can include Setup
    return any(part.lower() == 'setup' for part in path.parts)


def discover_tests_base(root: pathlib.Path) -> pathlib.Path:
    """(Deprecated) Previously found tests or test; retained for backward compatibility if needed."""
    tests = root / 'tests'
    if tests.exists() and tests.is_dir():
        return tests
    error("Could not find a 'tests' directory relative to current working directory.")
    raise RuntimeError


def parse_args():
    parser = argparse.ArgumentParser(description="Run dotnet tests with coverage.")
    parser.add_argument('path', nargs='?', help="Optional base path to search for test projects and store results")
    return parser.parse_args()


def collect_test_projects(base: pathlib.Path) -> list[pathlib.Path]:
    """Return list of .csproj files under base, excluding any path containing a Setup directory."""
    return [f for f in base.rglob('*.csproj') if f.is_file() and not is_setup_path(f)]


def main() -> int:
    args = parse_args()

    log('[STEP] 1/6 Resolve paths')
    cwd = pathlib.Path.cwd()
    if args.path:
        base_path = pathlib.Path(args.path).resolve()
        if not base_path.exists():
            error(f"Provided path does not exist: {base_path}")
        search_base = base_path
        test_results_path = base_path / 'TestResults'
        coverage_path = base_path / 'coverage-report'
    else:
        tests_dir = cwd / 'tests'
        if not tests_dir.exists():
            error("Could not find a 'tests' directory relative to current working directory.")
        search_base = tests_dir
        test_results_path = tests_dir / 'TestResults'
        docs_dir = cwd / 'docs'
        ensure_dir(docs_dir)
        coverage_path = docs_dir / 'coverage-report'

    log(f"[INFO] Search base path: {search_base}")
    log(f"[INFO] Test results path: {test_results_path}")
    log(f"[INFO] Coverage reports path: {coverage_path}")

    log('[STEP] 2/6 Prepare output directories')
    ensure_dir(test_results_path)
    ensure_dir(coverage_path)
    log('[INFO] Cleaning previous test results...')
    clean_dir(test_results_path)
    log('[INFO] Cleaning previous coverage reports...')
    clean_dir(coverage_path)
    log('[OK] Cleanup completed')

    log('[STEP] 3/6 Discover test projects')
    test_projects = collect_test_projects(search_base)
    if not test_projects:
        log('[WARN] No test projects found. Skipping test run.')
        log('[STEP] 6/6 Done')
        log('[SUCCESS] Test script completed')
        return 0
    log(f"[INFO] Found {len(test_projects)} test project(s)")

    log('[STEP] 4/6 Run tests with coverage collection')
    for tp in test_projects:
        log(f"[INFO] Running tests for project: {tp}")
        run(['dotnet', 'test', str(tp), "--collect:XPlat Code Coverage;Format=json,lcov,cobertura",
             "--results-directory", str(test_results_path)])

    log('[STEP] 5/6 Generate coverage report')
    reports_pattern = str(test_results_path / '**' / 'coverage.cobertura.xml')
    run(['reportgenerator', f"-reports:{reports_pattern}", f"-targetdir:{coverage_path}", '-reporttypes:Html'])
    log(f"[SUCCESS] Coverage report generated in {coverage_path}")

    log('[STEP] 6/6 Done')
    log('[SUCCESS] Test script completed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
