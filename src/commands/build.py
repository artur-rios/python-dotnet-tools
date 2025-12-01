"""
Build script:
  - Restores & builds solution under src
Usage:
  python build.py                        # builds default src path
  python build.py <path-to-src>          # builds a custom src directory
  python build.py --no-restore           # skip restore step
  python build.py --solution Name.sln    # specify solution when multiple exist
  python build.py --configuration Debug  # build specific configuration (Debug or Release)
"""
from __future__ import annotations
import sys, pathlib, subprocess
from typing import cast


def log(msg: str):
    print(msg)

def error(msg: str):
    log(f"[ERROR] {msg}")
    sys.exit(1)


def run(cmd: list[str], info: str | None = None):
    # Avoid printing the raw command line; optionally print a brief info message.
    if info:
        log(f"[INFO] {info}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        error(f"Command failed with exit code {e.returncode}.")


def resolve_target_dir(argv: list[str]) -> pathlib.Path:
    # Determine src path: first positional argument (non-flag), but skip the value after --solution and --configuration
    skip_next_for: str | None = None
    for a in argv[1:]:
        if skip_next_for is not None:
            skip_next_for = None
            continue
        if a in ('--solution', '--configuration'):
            skip_next_for = a
            continue
        if a.startswith('-'):
            continue
        # Ignore a stray token named 'build' (e.g., when called incorrectly)
        if a.lower() == 'build':
            continue
        # first non-flag positional arg is treated as path
        target = pathlib.Path(a).resolve()
        if not target.exists():
            error(f"Target path not found: '{target}'.")
        return target
    # No explicit path provided: use current working directory's 'src'
    default_src = (pathlib.Path.cwd() / 'src').resolve()
    if not default_src.exists():
        error("No 'src' folder found in the current working directory. Specify a path or run from a directory containing 'src'.")
    return default_src


def parse_flags(argv: list[str]) -> dict[str, object]:
    # Very simple flag parsing
    flags: dict[str, object] = {
        'no_restore': '--no-restore' in argv or '--noRestore' in argv,
        'solution': None,
        'configuration': None,
    }
    if '--solution' in argv:
        idx = argv.index('--solution')
        if idx + 1 >= len(argv) or argv[idx + 1].startswith('-'):
            error("--solution requires a solution file name, e.g. --solution ArturRios.Output.sln")
        flags['solution'] = argv[idx + 1]
    if '--configuration' in argv:
        idx = argv.index('--configuration')
        if idx + 1 >= len(argv) or argv[idx + 1].startswith('-'):
            error("--configuration requires a value: Debug or Release")
        cfg = argv[idx + 1]
        if cfg not in ('Debug', 'Release'):
            error("--configuration must be either 'Debug' or 'Release'")
        flags['configuration'] = cfg
    return flags


def pick_solution(target_path: pathlib.Path, solution_name: str | None) -> pathlib.Path:
    solutions = [f for f in target_path.glob('*.sln') if f.is_file()]
    if solution_name:
        # If a solution name is provided, validate and use it
        candidate = target_path / solution_name
        if candidate.exists() and candidate.is_file():
            return candidate
        # Try to match by name only (without path)
        matches = [s for s in solutions if s.name == solution_name]
        if matches:
            return matches[0]
        error(f"Specified solution '{solution_name}' was not found under '{target_path}'.")

    if not solutions:
        error("No solution (.sln) found under the target directory.")
    if len(solutions) > 1:
        names = ', '.join(s.name for s in solutions)
        error("Multiple solutions found under the target directory. "
              "Please specify one with --solution <name.sln>. Found: " + names)
    return solutions[0]


def build(target_path: pathlib.Path, no_restore: bool, solution_name: str | None, configuration: str | None) -> int:
    log("[INIT] Building...")
    log("[STEP] 1/4 Parse flags and arguments")
    log(f"[INFO] no_restore: {no_restore}")
    log(f"[INFO] solution: {solution_name if solution_name else '(auto)'}")
    log(f"[INFO] configuration: {configuration if configuration else '(Debug,Release)'}")

    log("[STEP] 2/4 Resolve target path")
    log(f"[INFO] Target path: '{target_path}'")
    if not target_path.exists():
        error(f"Target path not found: '{target_path}'.")

    log("[STEP] 3/4 Find solution at target path")
    solution = pick_solution(target_path, solution_name)
    log(f"[INFO] Solution detected: {solution.name}")

    log("[STEP] 4/4 Restore (optional) and build solution")
    if not no_restore:
        run(['dotnet', 'restore', str(solution)], info=f"Restoring solution: {solution.name}")

    # Build configurations: specified one or both
    configs = [configuration] if configuration else ['Debug', 'Release']
    for cfg in configs:
        build_cmd = ['dotnet', 'build', str(solution), '-c', cast(str, cfg)] + ([] if not no_restore else ['--no-restore'])
        run(build_cmd, info=f"Building solution: {solution.name} (Configuration: {cfg})")

    log("[SUCCESS] Build complete")
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv
    flags = parse_flags(argv)
    target = resolve_target_dir(argv)
    solution_name = flags['solution'] if isinstance(flags['solution'], str) else None
    configuration = flags['configuration'] if isinstance(flags['configuration'], str) else None
    return build(target, bool(flags['no_restore']), cast(str | None, solution_name), cast(str | None, configuration))
