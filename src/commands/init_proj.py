from __future__ import annotations
import argparse
import pathlib
import re
from importlib import resources


def log(msg: str):
    print(msg)


def error(msg: str):
    log(f"[ERROR] {msg}")
    raise SystemExit(1)


def _read_text(package: str, name: str) -> str:
    with resources.files(package).joinpath(name).open("r", encoding="utf-8") as f:
        return f.read()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a single project folder with minimal or NuGet csproj.")
    parser.add_argument("--name", required=False)
    parser.add_argument("--min", action="store_true")
    parser.add_argument("--nuget", action="store_true")
    if argv and argv[0] == "init-proj":
        argv = argv[1:]
    ns = parser.parse_args(argv)
    if not ns.name:
        error("--name is mandatory")
    if ns.min and ns.nuget:
        error("Do not specify both --min and --nuget")
    if not ns.min and not ns.nuget:
        ns.min = True
    return ns


def blank_nuget_metadata(content: str) -> str:
    # Replace placeholder tokens with empty strings
    content = (content
               .replace("__PACKAGE_ID__", "")
               .replace("__VERSION__", "")
               .replace("__AUTHOR__", "")
               .replace("__DESCRIPTION__", "")
               .replace("__REPOSITORY_URL__", "")
               .replace("__COMPANY__", ""))
    # Blank fixed metadata tags if present
    tags_to_blank = [
        "PackageLicenseExpression", "PackageReadmeFile", "Authors", "Company",
        "Description", "PackageId", "Version", "RepositoryUrl"
    ]
    for tag in tags_to_blank:
        content = re.sub(fr"<{tag}>.*?</{tag}>", f"<{tag}></{tag}>", content, flags=re.S)
    return content


def main(argv: list[str] | None = None) -> int:
    import sys
    if argv is None:
        argv = sys.argv[1:]
    ns = parse_args(argv)

    target_dir = pathlib.Path(ns.name).resolve()
    if target_dir.exists():
        error(f"Target directory already exists: {target_dir}")

    log("[INIT-PROJ] Creating project folder")
    target_dir.mkdir(parents=True, exist_ok=False)
    csproj_path = target_dir / f"{target_dir.name}.csproj"

    tpl_min = _read_text("commands._data", "templates/project.minimal.csproj.template")
    tpl_nuget = _read_text("commands._data", "templates/project.nuget.csproj.template")

    if ns.min:
        log("[MODE] minimal")
        content = tpl_min
    else:
        log("[MODE] nuget (blank metadata)")
        content = blank_nuget_metadata(tpl_nuget)

    csproj_path.write_text(content, encoding="utf-8")
    log(f"[OK] Created: {csproj_path}")
    log("[DONE] Project scaffold complete")
    log(f"Next: cd '{target_dir}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
