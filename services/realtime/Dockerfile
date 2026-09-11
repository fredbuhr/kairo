FROM node:22-alpine
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY services/realtime/package.json ./services/realtime/package.json
RUN pnpm --filter @kairo/realtime install --frozen-lockfile
COPY services/realtime ./services/realtime
WORKDIR /app/services/realtime
RUN pnpm build
EXPOSE 1234
CMD ["pnpm", "start"]
