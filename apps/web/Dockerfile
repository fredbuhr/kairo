FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml tsconfig.base.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm --filter @kairo/web install --frozen-lockfile
COPY apps/web ./apps/web
ARG VITE_KAIRO_API_URL=http://localhost:8000
ARG VITE_KEYCLOAK_URL=http://localhost:8081
ARG VITE_KEYCLOAK_REALM=kairo
ARG VITE_KEYCLOAK_CLIENT_ID=kairo-web
RUN pnpm --filter @kairo/web build
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS runtime
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/apps/web/dist ./dist
COPY apps/web/server.mjs ./server.mjs
USER node
EXPOSE 5173
CMD ["node", "server.mjs"]
