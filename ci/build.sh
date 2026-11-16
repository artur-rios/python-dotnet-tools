#!/bin/sh
# The `build` check: builds the package's sdist and wheel into dist/ (python -m build, from pyproject.toml and
# MANIFEST.in), installs the wheel, a pinned pytest and a pinned coverage into a throwaway virtual environment, then
# runs the test suite under coverage, with the floor pyproject.toml's [tool.coverage.report] sets. The unit tests fake
# every process; the end-to-end ones (marked e2e) scaffold .NET solutions in pytest's temporary directory and run the
# real dotnet, reportgenerator and git, so the image is the pinned .NET SDK, Python is added to it, and reportgenerator
# is installed as a pinned .NET tool. yggdrasil.yml runs it from the repository's root, as root, so it runs the same on
# your own machine:
#   docker run --rm -v "$PWD:/src" -w /src <yggdrasil.yml's build image> ci/build.sh
#
# The image (Ubuntu) has no Python: python3 and python3-venv come from its apt repositories when they are missing,
# which needs root (a machine of your own with them installed needs none). The scaffolded projects target net10.0 and
# take their NuGet packages' latest versions, as the templates say. build, pytest, coverage and reportgenerator are
# pinned to exact versions; the build backend is pyproject.toml's [build-system].
set -eu

# The repository's root, wherever this is run from.
cd "$(dirname "$0")/.."

# renovate: datasource=pypi depName=build
BUILD_VERSION=1.6.1
# renovate: datasource=pypi depName=pytest
PYTEST_VERSION=9.2.0
# renovate: datasource=pypi depName=coverage
COVERAGE_VERSION=7.13.1
# renovate: datasource=nuget depName=dotnet-reportgenerator-globaltool
REPORTGENERATOR_VERSION=5.5.12

export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

if ! python3 -m venv --help > /dev/null 2>&1; then
  if [ "$(id -u)" -ne 0 ]; then
    echo "ci/build.sh: python3 and python3-venv must be installed, and this is not run as root" >&2
    exit 1
  fi
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -qq --yes --no-install-recommends python3 python3-venv > /dev/null
fi

tools=$(mktemp -d)
trap 'rm -rf "$tools"' EXIT
dotnet tool install dotnet-reportgenerator-globaltool --version "$REPORTGENERATOR_VERSION" --tool-path "$tools/dotnet"
PATH="$tools/dotnet:$PATH"

python3 -m venv "$tools/venv"
"$tools/venv/bin/pip" install --quiet --disable-pip-version-check "build==$BUILD_VERSION"

rm -rf dist
"$tools/venv/bin/python" -m build --outdir dist .
"$tools/venv/bin/pip" install --quiet --disable-pip-version-check dist/*.whl \
  "pytest==$PYTEST_VERSION" "coverage==$COVERAGE_VERSION"

# No cache directory or coverage data file in the checkout.
export COVERAGE_FILE="$tools/.coverage"
"$tools/venv/bin/python" -m coverage run -m pytest -p no:cacheprovider
"$tools/venv/bin/python" -m coverage report
