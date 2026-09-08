.PHONY: bootstrap config prod-config ops-config up down all logs ps build check backup restore

bootstrap:
	@test -f .env || cp .env.example .env
	@echo "Created .env if it did not exist. Replace CHANGE_ME values before non-local use."

config: bootstrap
	docker compose config >/dev/null
	@echo "Development Compose configuration is valid."

prod-config:
	docker compose --env-file .env.production.example -f compose.yaml -f compose.production.yaml config >/dev/null
	@echo "Production Compose overlay is valid."

ops-config:
	docker compose --env-file .env.production.example -f compose.yaml -f compose.production.yaml -f compose.ops.yaml --profile ops config >/dev/null
	@echo "Operations/Restic Compose overlay is valid."

up: bootstrap
	docker compose up -d

all: bootstrap
	docker compose --profile finance --profile home --profile dev-agent --profile gpu --profile remote up -d

down:
	docker compose --profile finance --profile home --profile dev-agent --profile gpu --profile remote down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

build:
	pnpm build

backup: bootstrap
	bash scripts/ops/backup.sh

restore:
	bash scripts/ops/restore.sh $${SNAPSHOT:-latest}

check: config prod-config ops-config
	pnpm typecheck
