"""Compatibility wrapper for running the checker from the repository root."""

from story_checker.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
