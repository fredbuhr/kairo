.PHONY: bootstrap config up down all logs ps build check

bootstrap:
	@test -f .env || cp .env.example .env
	@echo "Created .env if it did not exist. Replace CHANGE_ME values before non-local use."

config: bootstrap
	docker compose config >/dev/null
	@echo "Compose configuration is valid."

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

check: config
	pnpm typecheck
