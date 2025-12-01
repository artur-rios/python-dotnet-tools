#!/usr/bin/env python3
"""
Clean script:
  - Removes all bin/ and obj/ directories under a target path
Behavior:
  - If a path argument is provided: clean that path; if it does not exist -> error & exit.
  - If no path argument is provided: attempt to use a 'src' directory located in the current working directory; if not found -> error & exit.
Usage:
  python clean.py                # cleans ./src if present
  python clean.py <path-to-src>  # cleans the provided directory
"""
from __future__ import annotations
import sys, pathlib, shutil


def log(msg: str):
    # Flush immediately so messages aren't lost prior to sys.exit on Windows shells
    print(msg, flush=True)

def error(msg: str):
    log(f"[ERROR] {msg}")
    sys.exit(1)


def remove_dir_tree(path: pathlib.Path):
    if path.is_dir():
        try:
            shutil.rmtree(path, ignore_errors=True)
            log(f"[OK] Removed directory: {path}")
        except Exception as e:
            log(f"[WARN] Failed to remove {path}: {e}")


def resolve_target_dir(argv: list[str]) -> pathlib.Path:
    """Resolve the target directory to clean following required behavior."""
    # If an argument is provided, use it directly (with common shorthand '.')
    if len(argv) > 1:
        raw = argv[1].strip().strip('"').strip("'")
        path = pathlib.Path.cwd() if raw in {'.', './'} else pathlib.Path(raw).expanduser()
        path = path.resolve()
        if not path.exists() or not path.is_dir():
            error(f"Provided path does not exist or is not a directory: '{path}'")
        return path
    # No argument: look for a 'src' directory in current working directory
    cwd = pathlib.Path.cwd()
    candidate = (cwd / 'src').resolve()
    if not candidate.exists() or not candidate.is_dir():
        error(
            "No path argument provided and 'src' directory was not found in current working directory.\n"
            f"Current working directory: '{cwd}'\n"
            "Usage: python clean.py [<path-to-src>]"
        )
    return candidate


def clean(target_path: pathlib.Path) -> int:
    log("[INIT] Cleaning...")
    log("[STEP] 1/3 Resolve target path")
    log(f"[INFO] Target path: '{target_path}'")
    if not target_path.exists() or not target_path.is_dir():
        error(
            f"Target directory not found: '{target_path}'.\n"
            f"Usage: python clean.py [<path-to-src>]\n"
            "Hint: provide an explicit path or ensure ./src exists."
        )
        return 1

    log("[STEP] 2/3 Scan and remove bin/ and obj/ folders")
    removed = 0
    for p in target_path.rglob('*'):
        if p.is_dir() and p.name in {'bin', 'obj'}:
            parent_name = p.parent.name
            log(f"[INFO] Cleaning {p.name} folder on project {parent_name}")
            remove_dir_tree(p)
            removed += 1
    log(f"[OK] Cleaned {removed} folders")

    log("[STEP] 3/3 Done")
    log("[SUCCESS] Clean complete")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Accept optional argv so console script entry point can call without parameters
    if argv is None:
        argv = sys.argv
    target = resolve_target_dir(argv)
    return clean(target)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
