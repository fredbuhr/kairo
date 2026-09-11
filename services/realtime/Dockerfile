FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml tsconfig.base.json ./
COPY services/realtime/package.json ./services/realtime/package.json
RUN pnpm --filter @kairo/realtime install --frozen-lockfile
COPY services/realtime ./services/realtime
WORKDIR /app/services/realtime
RUN pnpm build
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS runtime
ENV NODE_ENV=production
WORKDIR /app/services/realtime
COPY --from=build /app/node_modules /app/node_modules
COPY --from=build /app/services/realtime/node_modules ./node_modules
COPY --from=build /app/services/realtime/dist ./dist
COPY --from=build /app/services/realtime/package.json ./package.json
USER node
EXPOSE 1234
CMD ["node", "dist/index.js"]
