#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

docker compose config >/dev/null

echo "KAIRO foundation configuration is syntactically valid."
echo "Review CHANGE_ME values in .env before running make up."
