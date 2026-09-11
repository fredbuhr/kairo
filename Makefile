.PHONY: bootstrap identity config web-tools-config web-tools prod-config ops-config up down all logs ps build check backup restore

bootstrap:
	@test -f .env || cp .env.example .env
	@echo "Created .env if it did not exist. Replace CHANGE_ME values before non-local use."

identity:
	python scripts/smoke/identity_contract.py

config: bootstrap
	docker compose config >/dev/null
	@echo "Development Compose configuration is valid."

web-tools-config: bootstrap
	docker compose -f compose.yaml -f compose.web-mcp.yaml config >/dev/null
	@echo "Web MCP Compose overlay is valid."

web-tools: bootstrap
	docker compose -f compose.yaml -f compose.web-mcp.yaml up -d nevolium-web-mcp nevolium-core
	docker compose -f compose.yaml -f compose.web-mcp.yaml run --rm nevolium-worker python -m nevolium_worker.web_mcp_bootstrap
	@echo "Nevolium Web MCP tools are running and explicitly registered."

prod-config:
	python scripts/ops/production.py check --env-file $${NEVOLIUM_PRODUCTION_ENV:-.env.production}

prod-template:
	docker compose --env-file .env.production.example -f compose.yaml -f compose.production.yaml config >/dev/null
	@echo "Production Compose template syntax is valid; credentials/runtime are not validated."

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

check: identity config web-tools-config prod-template ops-config
	pnpm typecheck
