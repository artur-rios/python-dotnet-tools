from __future__ import annotations
import argparse
import json
import os
import pathlib
from datetime import datetime
from importlib import resources


def log(msg: str):
    print(msg)


def error(msg: str):
    log(f"[ERROR] {msg}")
    raise SystemExit(1)


def _read_text(package: str, name: str) -> str:
    with resources.files(package).joinpath(name).open("r", encoding="utf-8") as f:
        return f.read()


def _ensure_dir(p: pathlib.Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a minimal .NET library repository (no NuGet metadata).", add_help=True)
    parser.add_argument("--root")
    parser.add_argument("--solution")
    parser.add_argument("--project")
    parser.add_argument("--author")
    parser.add_argument("--description")
    parser.add_argument("--json", dest="json_path")
    if argv and argv[0] == "init-min":
        argv = argv[1:]
    return parser.parse_args(argv)


def load_params(ns: argparse.Namespace) -> dict:
    if ns.json_path:
        provided = {k: v for k, v in vars(ns).items() if k not in {"json_path"} and v is not None}
        if provided:
            error("Do not mix --json with other flags. Provide either a JSON file or flags, never both.")
        p = pathlib.Path(ns.json_path)
        if not p.exists():
            error(f"JSON file not found: {p}")
        return json.loads(p.read_text(encoding="utf-8"))
    raw = _read_text("commands._data", "parameters/init-parameters.json")
    return json.loads(raw)


def coalesce(curr: str | None, json_val: str | None) -> str | None:
    return curr or json_val


def main(argv: list[str] | None = None) -> int:
    import sys
    if argv is None:
        argv = sys.argv[1:]
    ns = parse_args(argv)
    params = load_params(ns)

    required = ["RootFolder", "SolutionName", "ProjectName", "Author", "Description"]
    missing = [k for k in required if not str(params.get(k, "")).strip()]
    if missing:
        error("Parameters JSON missing required properties: " + ", ".join(missing))

    root = coalesce(ns.root, params.get("RootFolder"))
    solution = coalesce(ns.solution, params.get("SolutionName"))
    project = coalesce(ns.project, params.get("ProjectName"))
    author = coalesce(ns.author, params.get("Author"))
    description = coalesce(ns.description, params.get("Description"))

    root_path = pathlib.Path(root).resolve()
    if root_path.exists():
        error(f"Target path already exists: {root_path}")
    if not solution:
        solution = root_path.name
    if not project:
        project = solution
    if not author:
        author = os.getenv("GIT_AUTHOR_NAME") or os.getenv("USER") or os.getenv("USERNAME") or "Unknown Author"
    if not description:
        description = f"{project} library"

    log("[INIT-MIN] Initializing minimal scaffold...")
    log("[STEP] 1/7 Parse and resolve inputs")
    log(f"[INFO] root: {root_path}")
    log(f"[INFO] solution: {solution}")
    log(f"[INFO] project: {project}")
    log(f"[INFO] author: {author}")
    log(f"[INFO] description: {description}")

    log("[STEP] 2/7 Create directory structure")
    _ensure_dir(root_path)
    src_dir = root_path / "src"
    docs_dir = root_path / "docs"
    tests_dir = root_path / "tests"
    for d in (src_dir, docs_dir, tests_dir):
        _ensure_dir(d)
    (docs_dir / ".gitkeep").write_text("", encoding="utf-8")
    (tests_dir / ".gitkeep").write_text("", encoding="utf-8")
    log("[OK] Created directories: src, docs, tests (with .gitkeep)")

    (root_path / ".wakatime-project").write_text(project, encoding="utf-8")
    log("[INFO] Wrote .wakatime-project")

    readme_tpl = _read_text("commands._data", "templates/README.md.template")
    readme = (
        readme_tpl
        .replace("__SOLUTION_NAME__", solution or "")
        .replace("__PROJECT_NAME__", project or "")
        .replace("__DESCRIPTION__", description or "")
    )
    log("[STEP] 3/7 Generate README")
    (root_path / "README.md").write_text(readme, encoding="utf-8")
    log("[OK] README created")

    log("[STEP] 4/7 Validate templates")
    editorconfig = _read_text("commands._data", "templates/.editorconfig.template")
    gitignore = _read_text("commands._data", "templates/.gitignore.template")
    license_tpl = _read_text("commands._data", "templates/LICENSE.MIT.template")
    proj_min_tpl = _read_text("commands._data", "templates/project.minimal.csproj.template")
    sln_tpl = _read_text("commands._data", "templates/solution.sln.template")
    log("[OK] All template files present")

    log("[STEP] 5/7 Copy template config files and LICENSE")
    (root_path / ".editorconfig").write_text(editorconfig, encoding="utf-8")
    (root_path / ".gitignore").write_text(gitignore, encoding="utf-8")
    year = datetime.now().year
    license_text = license_tpl.replace("__YEAR__", str(year)).replace("__AUTHOR__", author)
    (root_path / "LICENSE").write_text(license_text, encoding="utf-8")
    log("[OK] Config and LICENSE created")

    log("[STEP] 6/7 Generate project and solution")
    project_dir = src_dir / project
    _ensure_dir(project_dir)
    csproj_path = project_dir / f"{project}.csproj"
    csproj_path.write_text(proj_min_tpl, encoding="utf-8")

    import uuid
    solution_guid = str(uuid.uuid4()).upper()
    sln_rendered = (
        sln_tpl
        .replace("__PROJECT_NAME__", project)
        .replace("__PROJECT_GUID__", solution_guid)
        .replace("__SOLUTION_NAME__", solution)
    )
    (src_dir / f"{solution}.sln").write_text(sln_rendered, encoding="utf-8")
    log("[INFO] Project and solution created")

    (src_dir / "README.md").write_text(readme, encoding="utf-8")
    log("[OK] README copied to src")

    log("[STEP] 7/7 Done")
    log(f"[INFO] Solution path: {src_dir / (solution + '.sln')}")
    log(f"[INFO] Project path:  {csproj_path}")
    log("[SUCCESS] Minimal scaffold complete")
    log(f"Next: cd '{root_path}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
