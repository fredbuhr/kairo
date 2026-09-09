# KAIRO Core production policy for user-owned connector secrets.
#
# This policy is intentionally narrower than the root/dev token used by local compose fixtures.
# KAIRO Core may read/write values only under the managed per-user namespace allocated by Core and
# may read/delete KV-v2 metadata only to support explicit irreversible credential destruction.
# It does not grant list access to the whole mount, sys/admin capabilities, arbitrary secret paths,
# or access to test/legacy namespaces.

path "secret/data/kairo/users/*" {
  capabilities = ["create", "update", "read"]
}

path "secret/metadata/kairo/users/*" {
  capabilities = ["read", "delete"]
}
