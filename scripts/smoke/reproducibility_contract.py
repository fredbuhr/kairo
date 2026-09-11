from __future__ import annotations

import json
import re
import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "config" / "reproducibility-baseline.json"
IMAGE_RE = re.compile(r"^\s*image:\s*[\"']?([^\"'#\s]+)")


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _compose_images() -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()
    for path in sorted(ROOT.glob("compose*.yaml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = IMAGE_RE.match(line)
            if match:
                refs.add((_relative(path), match.group(1)))
    return refs


def _dockerfile_from(path: Path) -> str | None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.upper().startswith("FROM "):
            continue
        parts = line.split()
        index = 1
        if len(parts) > 2 and parts[1].startswith("--platform="):
            index = 2
        return parts[index]
    return None


def _dockerfile_images() -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()
    for path in sorted(ROOT.rglob("Dockerfile")):
        stages = set()
        for raw in path.read_text().splitlines():
            parts = raw.split()
            if not parts:
                continue
            if parts[0].upper() == "FROM":
                index = 2 if parts[1].startswith("--platform=") else 1
                ref = parts[index]
                if ref not in stages:
                    refs.add((_relative(path), ref))
                if len(parts) > index + 2 and parts[index + 1].upper() == "AS":
                    stages.add(parts[index + 2])
            if parts[0].upper() == "COPY":
                for part in parts:
                    if part.startswith("--from="):
                        ref = part.split("=", 1)[1]
                        if ref not in stages and not ref.isdecimal():
                            refs.add((_relative(path), ref))
    return refs


def _workflow_images() -> set[tuple[str, str]]:
    refs = set()
    options_with_value = {"--name", "--network", "--network-alias", "-v", "--volume", "-p", "--publish", "-e", "--env", "--entrypoint", "--user", "-u"}
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        content = path.read_text()
        for line in content.splitlines():
            match = IMAGE_RE.match(line)
            if match:
                refs.add((_relative(path), match.group(1)))
        # YAML block scalars and shell continuations both have indented following lines.
        for match in re.finditer(r"docker run (.*(?:\n[ ]{10,}.*)*)", content):
            words = shlex.split(match.group(0).replace("\\\n", " "))[2:]
            index = 0
            while index < len(words):
                token = words[index]
                if token in options_with_value:
                    index += 2
                elif token.startswith("-"):
                    index += 1
                else:
                    refs.add((_relative(path), token))
                    break
    return refs


def _find_install_files(needle: str) -> set[str]:
    found: set[str] = set()
    for path in sorted(ROOT.rglob("Dockerfile")):
        if needle in path.read_text(encoding="utf-8"):
            found.add(_relative(path))
    return found


def main() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    problems: list[str] = []

    package_manager = json.loads((ROOT / "package.json").read_text(encoding="utf-8")).get(
        "packageManager"
    )
    expected_package_manager = baseline["expected_package_manager"]
    if package_manager != expected_package_manager:
        problems.append(
            f"packageManager drift: expected {expected_package_manager!r}, got {package_manager!r}"
        )

    uv_config = tomllib.loads((ROOT / "uv.toml").read_text(encoding="utf-8"))
    uv_version = uv_config.get("required-version")
    expected_uv_version = baseline["expected_uv_version"]
    if uv_version != expected_uv_version:
        problems.append(
            f"uv toolchain drift: expected {expected_uv_version!r}, got {uv_version!r}"
        )

    required_lockfiles = set(baseline["required_lockfiles"])
    missing_lockfiles = sorted(path for path in required_lockfiles if not (ROOT / path).is_file())
    if missing_lockfiles:
        problems.append(f"required dependency lockfiles are missing: {missing_lockfiles}")

    all_images = _compose_images() | _dockerfile_images() | _workflow_images()
    actual_unpinned = {ref for ref in all_images if "@sha256:" not in ref[1]}
    expected_unpinned = {tuple(item) for item in baseline["known_unpinned_images"]}
    new_unpinned = sorted(actual_unpinned - expected_unpinned)
    retired_unpinned = sorted(expected_unpinned - actual_unpinned)
    if new_unpinned:
        problems.append(f"new unpinned image references: {new_unpinned}")
    if retired_unpinned:
        problems.append(
            "reproducibility baseline is stale; remove newly pinned/removed image debt: "
            f"{retired_unpinned}"
        )

    for relative_path, expected_image in baseline["validated_digest_pins"].items():
        path = ROOT / relative_path
        actual_image = _dockerfile_from(path)
        if actual_image != expected_image:
            problems.append(
                f"validated digest drift in {relative_path}: expected {expected_image!r}, "
                f"got {actual_image!r}"
            )

    validated_compose_pins = {
        tuple(item) for item in baseline.get("validated_compose_digest_pins", [])
    }
    invalid_compose_pins = sorted(
        ref
        for ref in validated_compose_pins
        if not ref[0].startswith("compose") or "@sha256:" not in ref[1]
    )
    if invalid_compose_pins:
        problems.append(
            "validated Compose image pins must name compose files and immutable digests: "
            f"{invalid_compose_pins}"
        )
    missing_compose_pins = sorted(validated_compose_pins - all_images)
    if missing_compose_pins:
        problems.append(f"validated Compose digest drift: {missing_compose_pins}")

    install_baseline = baseline["known_unlocked_install_files"]
    pnpm_actual = _find_install_files("pnpm install --no-frozen-lockfile")
    pnpm_expected = set(install_baseline["pnpm_no_frozen_lockfile"])
    if pnpm_actual != pnpm_expected:
        problems.append(
            "pnpm unlocked-install debt changed; update it explicitly: "
            f"expected={sorted(pnpm_expected)}, actual={sorted(pnpm_actual)}"
        )

    uv_actual = _find_install_files("uv pip install --system")
    uv_expected = set(install_baseline["uv_direct_install"])
    if uv_actual != uv_expected:
        problems.append(
            "uv direct-install debt changed; update it explicitly: "
            f"expected={sorted(uv_expected)}, actual={sorted(uv_actual)}"
        )

    locked_install_baseline = baseline["required_locked_install_files"]
    pnpm_locked_actual = _find_install_files("--frozen-lockfile")
    pnpm_locked_expected = set(locked_install_baseline["pnpm_frozen_lockfile"])
    if pnpm_locked_actual != pnpm_locked_expected:
        problems.append(
            "pnpm frozen container-install contract changed: "
            f"expected={sorted(pnpm_locked_expected)}, actual={sorted(pnpm_locked_actual)}"
        )

    uv_locked_actual = _find_install_files("uv sync --locked")
    uv_locked_expected = set(locked_install_baseline["uv_locked_sync"])
    if uv_locked_actual != uv_locked_expected:
        problems.append(
            "uv locked container-install contract changed: "
            f"expected={sorted(uv_locked_expected)}, actual={sorted(uv_locked_actual)}"
        )

    if problems:
        raise SystemExit("REPRODUCIBILITY CONTRACT FAILED:\n- " + "\n- ".join(problems))

    print(
        "REPRODUCIBILITY CONTRACT PASSED: canonical pnpm/uv lockfiles and toolchains are "
        "required, KAIRO container installs are frozen/locked, validated build and Compose "
        "digests are fixed, and all remaining unpinned-image debt exactly matches the "
        "explicit reproducibility baseline."
    )


if __name__ == "__main__":
    main()
