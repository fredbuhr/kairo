FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml tsconfig.base.json ./
COPY services/realtime/package.json ./services/realtime/package.json
RUN pnpm --filter @kairo/realtime install --frozen-lockfile
COPY services/realtime ./services/realtime
WORKDIR /app/services/realtime
RUN pnpm build
EXPOSE 1234
CMD ["pnpm", "start"]
