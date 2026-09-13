# Production-oriented template. The development Compose profile uses OpenBao dev mode.
ui = true

# OpenBao 2.6.2 no longer accepts disable_mlock; host memory/swap policy is an
# operator boundary, not a guarantee provided by this file-backed template.

storage "file" {
  path = "/openbao/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

api_addr = "http://openbao:8200"
