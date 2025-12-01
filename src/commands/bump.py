#!/usr/bin/env python3
"""
Bump project version script:
  - Accepts explicit version OR --major / --minor / --patch
  - Bumps the <Version> tag in a target .csproj passed explicitly OR auto-discovered
  - Auto-discovery: if no path argument is given, search for a single *.csproj under ./src relative to current working directory
  - If a second argument is a directory, search inside it (non-recursive) for a single *.csproj; if a file, it must be a .csproj
  - Validates MAJOR.MINOR.PATCH numeric format
  - Creates timestamped backup of csproj and deletes on successful verification
  - Only replaces numeric portion of existing <Version> tag; if missing inserts after <PackageId> line or first <PropertyGroup>
"""
from __future__ import annotations
import sys, re, shutil, datetime, pathlib

STEP_TOTAL = 9

def log(msg: str):
    print(msg)

def error(msg: str):
    log(f"[ERROR] {msg}")
    sys.exit(1)

def resolve_csproj(argv: list[str]) -> pathlib.Path:
    """Resolve the target .csproj based on optional second CLI argument.
    Rules:
      1) If argv has length >=3, treat argv[2] as path:
         - If it's a file: must exist and end with .csproj
         - If it's a directory: find exactly one immediate child *.csproj (non-recursive)
      2) If no second arg: look under CWD / 'src' for exactly one immediate child *.csproj
    Errors on zero or multiple matches.
    """
    # Second argument path (optional)
    csproj_path: pathlib.Path | None = None
    if len(argv) >= 3:
        supplied = pathlib.Path(argv[2]).expanduser()
        if not supplied.exists():
            error(f"Path not found: {supplied}")
        if supplied.is_file():
            if supplied.suffix.lower() != ".csproj":
                error(f"File is not a .csproj: {supplied}")
            csproj_path = supplied
        else:  # directory
            candidates = sorted(p for p in supplied.glob("*.csproj"))
            if not candidates:
                error(f"No .csproj file found in directory: {supplied}")
            if len(candidates) > 1:
                names = ", ".join(p.name for p in candidates)
                error(f"Multiple .csproj files found in directory (choose one explicitly): {names}")
            csproj_path = candidates[0]
    else:
        # Auto-discovery under ./src relative to current working directory
        search_dir = pathlib.Path.cwd() / "src"
        if not search_dir.exists() or not search_dir.is_dir():
            error(f"Auto-discovery failed: directory does not exist: {search_dir}")
        candidates = sorted(p for p in search_dir.glob("*.csproj"))
        if not candidates:
            error(f"Auto-discovery found no .csproj under: {search_dir}")
        if len(candidates) > 1:
            names = ", ".join(p.name for p in candidates)
            error(f"Auto-discovery found multiple .csproj files under {search_dir} (specify one explicitly): {names}")
        csproj_path = candidates[0]
    return csproj_path.resolve()

def read_current_version(csproj: pathlib.Path) -> str | None:
    raw = csproj.read_text(encoding="utf-8")
    m = re.search(r"<Version>(\d+\.\d+\.\d+)</Version>", raw)
    if m:
        return m.group(1)
    return None

def compute_target(arg: str, current: str | None) -> str:
    if arg in {"--major","--minor","--patch"} and current is None:
        error(f"{arg} requires existing version (<Version> tag missing in csproj)")
    if arg == "--major":
        major, minor, patch = map(int, current.split("."))
        return f"{major+1}.0.0"
    if arg == "--minor":
        major, minor, patch = map(int, current.split("."))
        return f"{major}.{minor+1}.0"
    if arg == "--patch":
        major, minor, patch = map(int, current.split("."))
        return f"{major}.{minor}.{patch+1}"
    return arg

def validate_version(v: str):
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        error(f"Invalid version format: {v}")

def create_backup(csproj: pathlib.Path) -> pathlib.Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup = csproj.with_name(csproj.name + f".bak.{timestamp}")
    shutil.copy2(csproj, backup)
    return backup

def insert_or_replace_version(raw: str, version: str) -> str:
    pattern = re.compile(r"(<Version>)(\d+\.\d+\.\d+)(</Version>)")
    if pattern.search(raw):
        # Replace only first occurrence; avoid backreference-number collision like \11
        return pattern.sub(lambda m: f"{m.group(1)}{version}{m.group(3)}", raw, count=1)
    # Need to insert
    pkg_pattern = re.compile(r"(<PackageId>.*?</PackageId>\s*)", re.DOTALL)
    m = pkg_pattern.search(raw)
    if m:
        insertion_point = m.end()
        indent = "    "
        return raw[:insertion_point] + f"{indent}<Version>{version}</Version>\n" + raw[insertion_point:]
    prop_pattern = re.compile(r"(<PropertyGroup>\s*)", re.DOTALL)
    m2 = prop_pattern.search(raw)
    if m2:
        insertion_point = m2.end()
        indent = "    "
        return raw[:insertion_point] + f"{indent}<Version>{version}</Version>\n" + raw[insertion_point:]
    # Fallback append (should not normally happen)
    return raw + f"\n    <Version>{version}</Version>\n"

def verify(csproj: pathlib.Path, version: str) -> bool:
    raw = csproj.read_text(encoding="utf-8")
    return f"<Version>{version}</Version>" in raw

def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv
    if len(argv) < 2:
        print("Usage: bump.py <version|--major|--minor|--patch> [<csproj-or-directory>]")
        return 1
    arg = argv[1]

    log("[STEP] 1/9 Resolve project file")
    csproj = resolve_csproj(argv)
    if not csproj.exists():
        error(f"Project file not found: {csproj}")
    log(f"[INFO] Target csproj: {csproj}")

    log("[STEP] 2/9 Read current version")
    current_version = read_current_version(csproj)
    if current_version:
        log(f"[INFO] Current version detected: {current_version}")
    else:
        log("[INFO] No existing <Version> tag detected.")

    log("[STEP] 3/9 Determine target version")
    target_version = compute_target(arg, current_version)
    if not target_version:
        error("Failed to compute target version")
    log(f"[INFO] Target version: {target_version}")

    log("[STEP] 4/9 Validate version format")
    validate_version(target_version)
    log("[OK] Format validated")

    log("[STEP] 5/9 Create backup")
    backup = create_backup(csproj)
    log(f"[OK] Backup created: {backup}")

    log("[STEP] 6/9 Update csproj (in-place, preserving formatting)")
    raw = csproj.read_text(encoding="utf-8")
    updated = insert_or_replace_version(raw, target_version)
    csproj.write_text(updated, encoding="utf-8")

    log("[STEP] 7/9 Verify change")
    matched = verify(csproj, target_version)
    if matched:
        log("[OK] Version tag verified in csproj")
    else:
        log("[WARN] Could not verify updated version tag.")

    log("[STEP] 8/9 Cleanup backup (if verified)")
    if matched:
        try:
            backup.unlink()
            log("[OK] Backup removed")
        except Exception:
            log(f"[WARN] Backup not deleted: {backup}")
    else:
        log(f"[INFO] Backup retained: {backup}")

    log("[STEP] 9/9 Done")
    log(f"[SUCCESS] Version bump complete: {target_version}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
