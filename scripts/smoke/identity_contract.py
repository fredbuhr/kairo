from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEGACY_TOKEN = "".join(("ka", "iro"))


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def require_text(path: str, *fragments: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise AssertionError(f"{path} is missing canonical identity fragments: {missing}")


def main() -> None:
    forbidden = LEGACY_TOKEN.casefold()
    path_hits: list[str] = []
    content_hits: list[str] = []

    for path in tracked_paths():
        relative = path.relative_to(ROOT).as_posix()
        if forbidden in relative.casefold():
            path_hits.append(relative)
        if forbidden.encode() in path.read_bytes().lower():
            content_hits.append(relative)

    if path_hits or content_hits:
        raise AssertionError(
            "legacy project identity remains in the tracked tree: "
            f"paths={path_hits}, contents={content_hits}"
        )

    require_text("pyproject.toml", 'name = "nevolium-workspace"')
    require_text(
        "services/core/pyproject.toml",
        'name = "nevolium-core"',
        'packages = ["src/nevolium_core"]',
    )
    require_text(
        "services/worker/pyproject.toml",
        'name = "nevolium-worker"',
        'packages = ["src/nevolium_worker"]',
    )
    require_text(
        "package.json",
        '"name": "nevolium"',
        "@nevolium/web",
        "@nevolium/realtime",
    )
    require_text(
        "compose.yaml",
        "name: nevolium",
        "  nevolium-core:",
        "  nevolium-worker:",
        "networks:\n  nevolium:",
    )
    require_text(
        "infrastructure/keycloak/nevolium-realm.json",
        '"realm": "nevolium"',
        '"clientId": "nevolium-web"',
        '"name": "nevolium-user"',
        '"name": "nevolium-admin"',
    )
    require_text(
        "infrastructure/openbao/policies/nevolium-core-read.hcl",
        'path "secret/data/nevolium/*"',
    )
    require_text(
        "services/core/src/nevolium_core/main.py",
        'FastAPI(title="Nevolium Core"',
        '"service": "nevolium-core"',
    )
    require_text("apps/web/index.html", "<title>Nevolium</title>")
    require_text(".env.example", "NEVOLIUM_ENV=development")

    print("Nevolium canonical identity contract passed")


if __name__ == "__main__":
    main()
