# The current Core resolves values/status; provisioning and erasure are operator actions.
# Workload scope, not per-user isolation: Core owns canonical ownership checks.
path "secret/data/nevolium/*" {
  capabilities = ["read"]
}

# The Core receives a periodic orphan token without the default policy. It may
# inspect and renew only its own token so the root token can remain offline.
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}
