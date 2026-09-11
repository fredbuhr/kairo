# The current Core resolves values/status; provisioning and erasure are operator actions.
# Workload scope, not per-user isolation: Core owns canonical ownership checks.
path "secret/data/nevolium/*" {
  capabilities = ["read"]
}
