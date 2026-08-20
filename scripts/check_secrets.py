#!/usr/bin/env python3

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "node_modules",
}
SKIP_FILES = {
    "pnpm-lock.yaml",
    "uv.lock",
}
TEXT_SUFFIXES = {
    ".cjs",
    ".js",
    ".json",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
SPECIAL_TEXT_FILES = {
    ".dockerignore",
    ".editorconfig",
    ".env.example",
    ".gitignore",
    ".npmrc",
    "Makefile",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}


def is_scannable(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return False
    return (
        path.name in SPECIAL_TEXT_FILES
        or path.suffix in TEXT_SUFFIXES
        or path.name.endswith(".Dockerfile")
    )


def git_tracked_files() -> set[str]:
    if not (ROOT / ".git").exists():
        return set()
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return {item.decode() for item in result.stdout.split(b"\0") if item}


def main() -> None:
    findings: list[str] = []
    tracked_files = git_tracked_files()
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        if path.is_dir():
            continue
        relative_path = path.relative_to(ROOT).as_posix()
        if path.name.startswith(".env") and path.name != ".env.example":
            if relative_path in tracked_files:
                findings.append(f"{relative_path}: committed environment file")
            continue
        if not is_scannable(path):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern_name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{relative_path}: matched {pattern_name}")

    if findings:
        print("\n".join(findings))
        raise SystemExit(1)
    print("secret scan: passed")


if __name__ == "__main__":
    main()
