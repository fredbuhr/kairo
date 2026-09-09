# KAIRO OpenBao boundary

Local development uses bootstrap/dev credentials so the compose stack can initialize itself. That is **not** the production trust model.

For production, KAIRO Core should receive a workload identity/token bound to `policies/kairo-core-user-secrets.hcl`. The policy intentionally permits only the operations Core currently needs for personal connector secrets:

- create/update/read KV-v2 data below `secret/data/kairo/users/*`;
- read/delete KV-v2 metadata below `secret/metadata/kairo/users/*` so explicit credential destruction can remove all versions.

It deliberately does not permit mount-wide listing, arbitrary `secret/*`, `sys/*`, `auth/*`, `sudo`, or legacy/test namespaces.

The public API never accepts an authenticated user's OpenBao path. Core allocates paths inside the managed user namespace and never returns the path in the `SecretReference` read model.

## Production provisioning outline

1. Enable/configure the KV-v2 `secret` mount according to the deployment.
2. Load `policies/kairo-core-user-secrets.hcl` as the KAIRO Core workload policy.
3. Bind that policy to the workload-auth mechanism chosen for the deployment (for example AppRole or an orchestrator-native identity integration).
4. Inject the resulting short-lived/renewable credential into KAIRO Core as `OPENBAO_TOKEN` (or replace the static-token adapter with the chosen workload-auth flow).
5. Do not reuse the local root/dev token in production.
6. Run `python scripts/smoke/openbao_policy_contract.py` in validation to ensure repository policy scope has not widened accidentally.

The policy source contract does not itself prove the deployed token is bound correctly. Deployment verification must confirm the live identity cannot access paths outside the managed KAIRO user-secret prefixes.
