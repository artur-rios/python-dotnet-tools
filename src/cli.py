from __future__ import annotations
import sys

from commands import build, clean, test, bump, tag


def main(argv: list[str] | None = None) -> int:
    """Entry point for console script `python-dotnet-tools`.
    Usage: python-dotnet-tools <command> [args]
    Commands: build, clean, test, bump, tag
    """
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print("Usage: python-dotnet-tools <build|clean|test|bump|tag> [args]")
        return 0
    cmd, *rest = argv
    if cmd == "build":
        return build.main(["build"] + rest)
    if cmd == "clean":
        return clean.main(["clean"] + rest)
    if cmd == "test":
        return test.main()
    if cmd == "bump":
        return bump.main(["bump"] + rest)
    if cmd == "tag":
        return tag.main(["tag"] + rest)
    print(f"Unknown command: {cmd}")
    print("Usage: python-dotnet-tools <build|clean|test|bump|tag> [args]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
