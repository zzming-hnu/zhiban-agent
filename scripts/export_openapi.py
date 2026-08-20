#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from zhiban.core.config import Settings  # noqa: E402
from zhiban.main import create_app  # noqa: E402


def render_openapi() -> str:
    app = create_app(Settings(app_env="test", app_version="0.1.0"))
    document: dict[str, Any] = app.openapi()
    return f"{json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export deterministic FastAPI OpenAPI JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "packages/contracts/openapi.json",
    )
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_openapi(), encoding="utf-8")
    print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
