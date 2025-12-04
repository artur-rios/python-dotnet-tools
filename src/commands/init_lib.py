from __future__ import annotations
import argparse
import json
import os
import pathlib
import subprocess
from datetime import datetime
from importlib import resources


def log(msg: str):
    print(msg)


def error(msg: str):
    log(f"[ERROR] {msg}")
    raise SystemExit(1)


def _read_text(package: str, name: str) -> str:
    try:
        with resources.files(package).joinpath(name).open("r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        error(f"Embedded resource not found: {package}/{name}")
        return ""


def _ensure_dir(p: pathlib.Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _git_repo_url() -> str:
    try:
        res = subprocess.run([
            "git", "remote", "get-url", "origin"
        ], capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a new .NET library repository structure (NuGet metadata).", add_help=True)
    parser.add_argument("--root")
    parser.add_argument("--solution")
    parser.add_argument("--project")
    parser.add_argument("--author")
    parser.add_argument("--company")
    parser.add_argument("--description")
    parser.add_argument("--version")
    parser.add_argument("--packageId")
    parser.add_argument("--repositoryUrl")
    parser.add_argument("--json", dest="json_path")
    # Allow being called via dispatcher with leading token 'init-lib'
    if argv and argv[0] == "init-lib":
        argv = argv[1:]
    return parser.parse_args(argv)


def load_params(ns: argparse.Namespace) -> dict:
    # Default to embedded parameters/init-parameters.json when --json not provided
    params: dict
    if ns.json_path:
        # Disallow mixing with flags
        provided = {k: v for k, v in vars(ns).items() if k not in {"json_path"} and v is not None}
        if provided:
            error("Do not mix --json with other flags. Provide either a JSON file or flags, never both.")
        p = pathlib.Path(ns.json_path)
        if not p.exists():
            error(f"JSON file not found: {p}")
        try:
            params = json.loads(p.read_text(encoding="utf-8"))
        except Exception as ex:
            error(f"Failed to parse JSON: {p} ({ex})")
    else:
        raw = _read_text("commands._data", "parameters/init-parameters.json")
        try:
            params = json.loads(raw)
        except Exception as ex:
            error(f"Failed to parse embedded parameters JSON: {ex}")

    required = [
        "RootFolder", "SolutionName", "ProjectName", "Author", "Company",
        "Description", "PackageId", "RepositoryUrl", "PackageLicenseExpression", "Version",
    ]
    missing = [k for k in required if not str(params.get(k, "")).strip()]
    if missing:
        error("Parameters JSON missing required properties: " + ", ".join(missing))
    return params


def coalesce(curr: str | None, json_val: str | None) -> str | None:
    return curr or json_val


def main(argv: list[str] | None = None) -> int:
    import sys
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)
    params = load_params(args)

    root = coalesce(args.root, params.get("RootFolder"))
    solution = coalesce(args.solution, params.get("SolutionName"))
    project = coalesce(args.project, params.get("ProjectName"))
    author = coalesce(args.author, params.get("Author"))
    company = coalesce(args.company, params.get("Company"))
    description = coalesce(args.description, params.get("Description"))
    version = coalesce(args.version, params.get("Version"))
    package_id = coalesce(args.packageId, params.get("PackageId"))
    repo_url = coalesce(args.repositoryUrl, params.get("RepositoryUrl"))

    # Resolve defaults
    root_path = pathlib.Path(root).resolve()
    if root_path.exists():
        error(f"Target path already exists: {root_path}")
    if not solution:
        solution = root_path.name
    if not project:
        project = solution
    if not author:
        author = os.getenv("GIT_AUTHOR_NAME") or os.getenv("USER") or os.getenv("USERNAME") or "Unknown Author"
    if not company:
        company = author
    if not description:
        description = f"{project} library"
    if not package_id:
        package_id = project
    if not repo_url:
        repo_url = _git_repo_url()

    log("[INIT-LIB] Initializing scaffold...")
    log("[STEP] 1/9 Parse and resolve inputs")
    log(f"[INFO] root: {root_path}")
    log(f"[INFO] solution: {solution}")
    log(f"[INFO] project: {project}")
    log(f"[INFO] packageId: {package_id}")
    log(f"[INFO] author: {author}")
    log(f"[INFO] company: {company}")
    log(f"[INFO] version: {version}")
    log(f"[INFO] description: {description}")

    log("[STEP] 2/9 Create directory structure")
    _ensure_dir(root_path)
    src_dir = root_path / "src"
    docs_dir = root_path / "docs"
    tests_dir = root_path / "tests"
    for d in (src_dir, docs_dir, tests_dir):
        _ensure_dir(d)
    (docs_dir / ".gitkeep").write_text("", encoding="utf-8")
    log("[OK] Created directories: src, docs, tests")

    # wakatime
    (root_path / ".wakatime-project").write_text(project, encoding="utf-8")
    log("[INFO] Wrote .wakatime-project")

    log("[STEP] 3/9 Validate templates")
    # Read embedded templates
    editorconfig = _read_text("commands._data", "templates/.editorconfig.template")
    gitignore = _read_text("commands._data", "templates/.gitignore.template")
    license_tpl = _read_text("commands._data", "templates/LICENSE.MIT.template")
    proj_tpl = _read_text("commands._data", "templates/project.nuget.csproj.template")
    sln_tpl = _read_text("commands._data", "templates/solution.sln.template")
    tests_tpl = _read_text("commands._data", "templates/project.Tests.csproj.template")
    log("[OK] All template files present")

    log("[STEP] 4/9 Copy template config files")
    (root_path / ".editorconfig").write_text(editorconfig, encoding="utf-8")
    (root_path / ".gitignore").write_text(gitignore, encoding="utf-8")
    log("[OK] Config files copied")

    log("[STEP] 5/9 Generate README and LICENSE")
    readme_tpl = _read_text("commands._data", "templates/README.md.template")
    readme = (
        readme_tpl
        .replace("__SOLUTION_NAME__", solution or "")
        .replace("__PROJECT_NAME__", project or "")
        .replace("__DESCRIPTION__", description or "")
        .replace("__REPOSITORY_URL__", repo_url or "")
        .replace("__PACKAGE_ID__", (package_id or ""))
        .replace("__AUTHOR__", author or "")
        .replace("__COMPANY__", company or "")
    )
    (root_path / "README.md").write_text(readme, encoding="utf-8")
    year = datetime.now().year
    license_text = license_tpl.replace("__YEAR__", str(year)).replace("__AUTHOR__", author)
    (root_path / "LICENSE").write_text(license_text, encoding="utf-8")
    log("[OK] README and LICENSE created")

    log("[STEP] 6/9 Generate project and solution")
    csproj_path = src_dir / f"{project}.csproj"
    proj_rendered = (
        proj_tpl
        .replace("__PACKAGE_ID__", package_id)
        .replace("__VERSION__", version or "")
        .replace("__AUTHOR__", author)
        .replace("__DESCRIPTION__", description)
        .replace("__REPOSITORY_URL__", repo_url or "")
        .replace("__COMPANY__", company)
    )
    csproj_path.write_text(proj_rendered, encoding="utf-8")
    log("[INFO] Project file created")

    # Render solution with project path adjustment (project directly under src)
    import uuid
    solution_guid = str(uuid.uuid4()).upper()
    sln_rendered = (
        sln_tpl
        .replace("__PROJECT_NAME__", project)
        .replace("__PROJECT_GUID__", solution_guid)
        .replace("__SOLUTION_NAME__", solution)
    )
    old_rel = f"{project}\\{project}.csproj"
    if old_rel in sln_rendered:
        sln_rendered = sln_rendered.replace(old_rel, f"{project}.csproj")
    (src_dir / f"{solution}.sln").write_text(sln_rendered, encoding="utf-8")
    log("[INFO] Solution file created")

    log("[STEP] 7/9 Generate test project")
    tests_csproj = tests_tpl.replace("__PROJECT_NAME__", project)
    (tests_dir / f"{project}.Tests.csproj").write_text(tests_csproj, encoding="utf-8")
    log("[INFO] Test project file created")

    log("[STEP] 8/9 Copy README next to project")
    (src_dir / "README.md").write_text(readme, encoding="utf-8")
    log("[OK] README copied to src")

    log("[STEP] 9/9 Done")
    log(f"[INFO] Solution path: {src_dir / (solution + '.sln')}")
    log(f"[INFO] Project path:  {csproj_path}")
    log("[SUCCESS] Scaffold complete")
    log(f"Next: cd '{root_path}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
