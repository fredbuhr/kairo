# The current Core resolves values/status; provisioning and erasure are operator actions.
# Workload scope, not per-user isolation: Core owns canonical ownership checks.
path "secret/data/nevolium/*" {
  capabilities = ["read"]
}

# The Core receives a periodic orphan token without the default policy. The
# bootstrap may inspect this token's effective capabilities without granting
# access to another identity; runtime renewal remains self-scoped.
path "sys/capabilities-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}
