from __future__ import annotations

import json
import re
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
        image = _dockerfile_from(path)
        if image:
            refs.add((_relative(path), image))
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

    all_images = _compose_images() | _dockerfile_images()
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

    expected_missing = set(baseline["known_missing_lockfiles"])
    still_missing = {path for path in expected_missing if not (ROOT / path).exists()}
    if still_missing != expected_missing:
        newly_present = sorted(expected_missing - still_missing)
        problems.append(
            "lockfile debt has improved; promote the new lockfile(s) by updating the baseline: "
            f"{newly_present}"
        )

    if problems:
        raise SystemExit("REPRODUCIBILITY CONTRACT FAILED:\n- " + "\n- ".join(problems))

    print(
        "REPRODUCIBILITY CONTRACT PASSED: validated build digests are fixed, the pnpm "
        "toolchain is fixed, and all remaining unpinned-image/unlocked-install/lockfile "
        "debt exactly matches the explicit G50 baseline."
    )


if __name__ == "__main__":
    main()
