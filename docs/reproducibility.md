# KAIRO reproducibility policy

KAIRO treats reproducibility as a progressive hardening boundary, not as a claim that every upstream dependency is already immutable.

## G50 baseline rule

The validated G49 runtime is the reference point for the first reproducibility baseline. G50 makes that state explicit in `config/reproducibility-baseline.json` and enforces it with `scripts/smoke/reproducibility_contract.py`.

The contract has two jobs:

1. preserve immutable inputs that have actually been validated;
2. prevent existing reproducibility debt from silently growing.

A dependency or image should not be changed merely to make the contract green. If a reference is upgraded, pinned, removed or newly introduced, update the baseline in the same reviewed change and run the relevant integration tests.

## What is immutable now

The Core and Worker `uv` build image is pinned by SHA-256 digest to the exact image observed in the all-green G49 validation run. The root JavaScript package-manager version is also explicit (`pnpm@10.15.1`).

## Explicit remaining debt

The baseline records every current Compose/Docker image reference that is still tag-based rather than digest-based. This includes normal version tags as well as clearly moving channels such as `latest`, `stable` and `main-latest`. Optional specialist profiles are tracked too; their presence in the file does **not** mean they are production-approved.

The repository also currently lacks resolver-generated lockfiles for the JavaScript workspace and the Core/Worker Python projects. Their absence is tracked explicitly:

- `pnpm-lock.yaml`;
- `services/core/uv.lock`;
- `services/worker/uv.lock`.

The web/realtime Dockerfiles still use `pnpm install --no-frozen-lockfile`, and Core/Worker still resolve Python application dependencies during image build. These are known G50 debts, not desired end-state behavior.

## Promotion rule

Do not fabricate lockfiles or guess image digests. A lockfile must be produced by the real package resolver from the repository manifests. An image digest should be captured from a build/test path that KAIRO actually validates.

When debt is retired, the CI contract intentionally fails until the retired entry is removed from the baseline. This forces reproducibility improvements to be recorded as first-class changes instead of silently changing the meaning of the baseline.

## Production target

Before KAIRO is treated as production/commercial-ready, the hardening block should include:

- resolver-generated lockfiles used in frozen/offline-capable install paths where practical;
- immutable digests for production container images;
- controlled dependency/image update automation;
- SBOM and vulnerability/license scanning;
- reproducible build metadata tied to the deployed KAIRO release;
- upgrade and rollback drills using the same canonical backup/recovery boundaries.
