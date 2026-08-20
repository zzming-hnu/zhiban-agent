#!/usr/bin/env python3

import difflib
import subprocess
import sys
import tempfile
from pathlib import Path

from export_openapi import ROOT, render_openapi


def compare_file(expected_path: Path, actual_path: Path) -> bool:
    expected = expected_path.read_text(encoding="utf-8")
    actual = actual_path.read_text(encoding="utf-8")
    if expected == actual:
        return True

    diff = difflib.unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        fromfile=str(expected_path.relative_to(ROOT)),
        tofile=f"regenerated/{expected_path.name}",
        lineterm="",
    )
    print("\n".join(diff))
    return False


def main() -> None:
    committed_openapi = ROOT / "packages/contracts/openapi.json"
    committed_types = ROOT / "packages/contracts/src/api.ts"

    with tempfile.TemporaryDirectory(prefix="zhiban-contracts-") as temp_directory:
        temporary_root = Path(temp_directory)
        generated_openapi = temporary_root / "openapi.json"
        generated_types = temporary_root / "api.ts"
        generated_openapi.write_text(render_openapi(), encoding="utf-8")

        subprocess.run(
            [
                "corepack",
                "pnpm",
                "--filter",
                "@zhiban/contracts",
                "exec",
                "openapi-typescript",
                str(generated_openapi),
                "-o",
                str(generated_types),
            ],
            cwd=ROOT,
            check=True,
        )

        openapi_matches = compare_file(committed_openapi, generated_openapi)
        types_match = compare_file(committed_types, generated_types)
        if not openapi_matches or not types_match:
            print("contract drift detected; run `make contracts`", file=sys.stderr)
            raise SystemExit(1)

    print("contract drift check: passed")


if __name__ == "__main__":
    main()
