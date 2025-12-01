# Python Dotnet Tools

A lightweight Python CLI that streamlines common .NET project workflows: build, clean, test with coverage, bump versions, and create git tags.

The CLI exposes a single dispatcher command `python-dotnet-tools` and direct convenience commands for each action:

- `python-dotnet-build`
- `python-dotnet-clean`
- `python-dotnet-test`
- `python-dotnet-bump`
- `python-dotnet-tag`

## Features

- Build .NET solutions (restore optional, configuration selection)
- Clean `bin/` and `obj/` folders across a tree
- Run tests and generate HTML coverage reports (via `reportgenerator`)
- Bump a project version in `.csproj` (semantic versioning helpers)
- Create and optionally push annotated git tags from `.csproj` version

## Folder structure

```txt
python-dotnet-tools/
├─ pyproject.toml
├─ README.md
└─ src/
   ├─ cli.py                  # main dispatcher for python-dotnet-tools
   └─ commands/
      ├─ build.py             # build solution(s)
      ├─ clean.py             # remove bin/ and obj/
      ├─ test.py              # run tests + coverage
      ├─ bump.py              # bump <Version> in .csproj
      └─ tag.py               # create git tag from version
```

## Prerequisites

- Python 3.11+ (see `requires-python` in `pyproject.toml`)
- .NET SDK installed and available on PATH (`dotnet` command)
  - Windows: `winget install Microsoft.DotNet.SDK.10` or download from <https://dotnet.microsoft.com/download>
  - Linux: install via your distro (e.g., Ubuntu `sudo apt-get install dotnet-sdk-10.0`, Fedora `sudo dnf install dotnet-sdk-10.0`) or follow official instructions
- Git installed (for tagging and pushing)
- reportgenerator installed (for coverage HTML reports)
  - Dotnet CLI (cross-platform): `dotnet tool install -g dotnet-reportgenerator-globaltool`
  - Windows: `winget install danielpalme.reportgenerator` or `scoop install reportgenerator` or `choco install reportgenerator`
  - Linux: via package manager if available, or download binaries from [GitHub repository](https://github.com/danielpalme/ReportGenerator/releases)

## Installation

You can install the Python package from source using `pip`. From the repository root:

- Editable (recommended for development):

```cmd
pip install -e .
```

- Regular install (build and install):

```cmd
pip install .
```

After installation, console scripts will be available on your PATH:

- `python-dotnet-tools`
- `python-dotnet-build`, `python-dotnet-clean`, `python-dotnet-test`, `python-dotnet-bump`, `python-dotnet-tag`

Ensure prerequisites are on PATH:

- `dotnet` (from .NET SDK)
- `reportgenerator` (either the standalone binary or the dotnet global tool; if installed as a dotnet tool, it’s available as `reportgenerator` once your dotnet tools path is on PATH)

Alternatively, you can run the dispatcher module directly during development:

```cmd
python -m src.cli --help
```

## Usage

You can use either the single dispatcher or the dedicated commands. All commands support `--help`.

Notes:

- You can call any command via the dispatcher too. For example, instead of `python-dotnet-build`, you can run `python-dotnet-tools build` (and similarly: `python-dotnet-tools clean`, `python-dotnet-tools test`, etc.).

### Dispatcher

```cmd
python-dotnet-tools --help
python-dotnet-tools <build|clean|test|bump|tag> [args]
```

### Build

Builds a solution found under the target directory.

- Default target path (no arg): `./src` under current working directory
- If multiple `.sln` files are present, you must specify one with `--solution`

Examples:

```cmd
python-dotnet-build                             # restore + build Debug and Release under ./src
python-dotnet-build .                           # build current directory’s ./src
python-dotnet-build D:\path\to\repo\src         # build a specific src directory
python-dotnet-build --no-restore                # skip restore
python-dotnet-build --solution MyApp.sln        # specify solution
python-dotnet-build --configuration Release     # build only Release
```

Flags:

- `--no-restore` Skip `dotnet restore`
- `--solution <name.sln>` Pick a specific solution when multiple exist
- `--configuration <Debug|Release>` Build a specific configuration; default builds both

### Clean

Removes all `bin/` and `obj/` directories under the target path.

Examples:

```cmd
python-dotnet-clean                 # cleans ./src under current working directory
python-dotnet-clean .               # cleans the current directory (expects ./src)
python-dotnet-clean D:\code\proj   # cleans the provided directory
```

### Test

Discovers test projects and runs `dotnet test` with coverage; generates HTML report via `reportgenerator`.

- With a path arg: results and coverage are created under that path
- Without a path arg: looks for `./tests` and writes coverage to `./docs/coverage-report`

Examples:

```cmd
python-dotnet-test                         # search ./tests, write results to ./tests/TestResults, HTML to ./docs/coverage-report
python-dotnet-test D:\code\proj\tests      # search under given path, write TestResults/ and coverage-report/ there
```

Outputs:

- Test results: `TestResults/`
- Coverage report: `coverage-report/` (or `docs/coverage-report/` when no path provided)

### Bump

Bumps a version in a target `.csproj` by replacing or inserting a `<Version>` tag.

- Version sources: explicit `MAJOR.MINOR.PATCH` or helpers `--major|--minor|--patch`
- Target selection: explicit `.csproj` file or directory (non-recursive) with a single `.csproj`; otherwise auto-discovered under `./src`

Examples:

```cmd
python-dotnet-bump 1.2.3                          # set version to 1.2.3 (auto-discover csproj under ./src)
python-dotnet-bump --minor ./src/MyApp            # bump minor in a single .csproj under provided directory
python-dotnet-bump --patch D:\code\MyApp.csproj   # bump patch in an explicit csproj
```

Rules:

- `--major|--minor|--patch` require an existing `<Version>` tag
- Explicit version must match `MAJOR.MINOR.PATCH`
- Creates a timestamped backup and removes it after successful verification

### Tag

Creates an annotated git tag from the version read in a `.csproj`.

- Default base path: `./src`
- If multiple `.csproj` files are found, provide a more specific path
- Optional push to remote with `--push` and `--remote`

Examples:

```cmd
python-dotnet-tag                             # tag from version read under ./src (e.g., v1.2.3)
python-dotnet-tag D:\code\proj                # tag from version read under given path
python-dotnet-tag --push                      # push to origin
python-dotnet-tag --push --remote upstream    # push to custom remote
```

Notes:

- If tag already exists, the command aborts

## Configuration

No project-specific config file is required.

- You may keep local environment variables in a `.env` file for other tools; this project does not read it.

## Development

Set up a virtual environment and install the package in editable mode.

Windows PowerShell:

```cmd
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Run commands locally:

```cmd
python -m src.cli --help
python-dotnet-tools build --help
```

## License

MIT (see `pyproject.toml`). A copy of the license is available at `LICENSE` in the repository.
