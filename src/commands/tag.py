#!/usr/bin/env python3
"""
Tag script:
  - Searches for a .csproj under a target path
  - Reads the <Version> property from the project file
  - Creates an annotated git tag based on that version (e.g., v1.2.3)
  - If a path argument is provided: use it as the base search path; if it does not exist -> error & exit.
  - If no path argument is provided: attempt to use a 'src' directory located in the current working directory; if not found -> error & exit.
  - If multiple .csproj files are found: error and ask to provide a specific path.
  - Optional flags:
      * --push                Send the created tag to the remote (defaults to 'origin')
      * --remote <name>       Choose a remote name (used only when --push is present)
Usage:
  python tag.py                        # searches ./src for a single .csproj and tags
  python tag.py <path>                 # searches <path> for a single .csproj and tags
  python tag.py --push                 # tag and push to origin
  python tag.py <path> --push --remote upstream
"""
from __future__ import annotations
import sys, pathlib, subprocess, xml.etree.ElementTree as ET
from typing import Tuple


def log(msg: str):
    print(msg)


def error(msg: str):
    log(f"[ERROR] {msg}")
    sys.exit(1)


def run(cmd: list[str], info: str | None = None):
    if info:
        log(f"[INFO] {info}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        error(f"Command failed with exit code {e.returncode}.")


def resolve_base_path(argv: list[str]) -> pathlib.Path:
    # If an argument is provided (argv[1]), use it; else default to ./src
    # Skip flags like --push and --remote
    positional: pathlib.Path | None = None
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == '--remote':
            i += 2
            continue
        if a.startswith('-'):
            i += 1
            continue
        positional = pathlib.Path(a).expanduser().resolve()
        break
    if positional is not None:
        if not positional.exists() or not positional.is_dir():
            error(f"Provided path does not exist or is not a directory: '{positional}'")
        return positional
    default_src = (pathlib.Path.cwd() / 'src').resolve()
    if not default_src.exists() or not default_src.is_dir():
        error("No path argument provided and 'src' directory was not found in current working directory.")
    return default_src


def parse_flags(argv: list[str]) -> Tuple[bool, str]:
    """Return (push, remote_name)."""
    push = any(a == '--push' for a in argv[1:])
    remote = 'origin'
    if '--remote' in argv:
        idx = argv.index('--remote')
        if idx + 1 >= len(argv) or argv[idx + 1].startswith('-'):
            error("--remote requires a remote name, e.g. --remote origin")
        remote = argv[idx + 1]
    return push, remote


def find_single_csproj(base: pathlib.Path) -> pathlib.Path:
    csprojs = [p for p in base.rglob('*.csproj') if p.is_file()]
    if not csprojs:
        error(f"No .csproj file found under '{base}'.")
    if len(csprojs) > 1:
        names = ', '.join(p.name for p in csprojs[:5]) + ("..." if len(csprojs) > 5 else "")
        error("Multiple .csproj files found. Please provide a more specific path. Found: " + names)
    return csprojs[0]


def read_version_from_csproj(csproj: pathlib.Path) -> str:
    try:
        tree = ET.parse(csproj)
        root = tree.getroot()
        # .csproj typically uses MSBuild XML namespace, but often Version is non-namespaced.
        # We'll search both namespaced and non-namespaced tags.
        # Gather potential Version elements under any PropertyGroup.
        version: str | None = None
        for pg in root.findall('.//PropertyGroup'):
            v = pg.find('Version')
            if v is not None and v.text:
                version = v.text.strip()
                break
        if version:
            return version
        # Namespace-aware fallback: try any element ending with 'Version'
        for elem in root.iter():
            if elem.tag.endswith('Version') and elem.text:
                version = elem.text.strip()
                if version:
                    return version
        error(f"Could not find <Version> property in '{csproj}'.")
    except ET.ParseError as e:
        error(f"Failed to parse csproj '{csproj}': {e}")
    raise RuntimeError("Unreachable")


def create_git_tag(version: str) -> str:
    tag_name = f"v{version}"
    # Check if tag already exists
    try:
        res = subprocess.run(['git', 'rev-parse', '--verify', tag_name], capture_output=True)
        if res.returncode == 0:
            error(f"Tag '{tag_name}' already exists.")
    except Exception:
        # If git isn't available or repo not initialized, let the subsequent tag command error with a clearer message
        pass
    run(['git', 'tag', '-a', tag_name, '-m', f"Release {version}"], info=f"Creating git tag {tag_name}")
    return tag_name


def push_git_tag(tag_name: str, remote: str) -> None:
    run(['git', 'push', remote, tag_name], info=f"Pushing git tag {tag_name} to remote '{remote}'")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv
    log("[INIT] Tagging...")
    log("[STEP] 1/5 Parse flags and resolve base path")
    push, remote = parse_flags(argv)
    base = resolve_base_path(argv)
    log(f"[INFO] Base path: '{base}'")
    log(f"[INFO] push: {push}")
    log(f"[INFO] remote: {remote}")

    log("[STEP] 2/5 Locate project file (.csproj)")
    csproj = find_single_csproj(base)
    log(f"[INFO] Project file: {csproj}")

    log("[STEP] 3/5 Read version from project")
    version = read_version_from_csproj(csproj)
    log(f"[INFO] Version: {version}")

    log("[STEP] 4/5 Create git tag")
    tag_name = create_git_tag(version)

    if push:
        log("[STEP] 5/5 Push tag to remote")
        push_git_tag(tag_name, remote)
        log("[SUCCESS] Tag created and pushed")
    else:
        log("[STEP] 5/5 Done")
        log("[SUCCESS] Tag created")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
