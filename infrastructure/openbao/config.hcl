# Production-oriented template. The development Compose profile uses OpenBao dev mode.
ui = true

disable_mlock = false

storage "file" {
  path = "/openbao/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

api_addr = "http://openbao:8200"
