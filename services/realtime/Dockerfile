FROM node:22-alpine
WORKDIR /app
RUN corepack enable
COPY package.json tsconfig.json ./
COPY src ./src
RUN pnpm install --no-frozen-lockfile && pnpm build
EXPOSE 1234
CMD ["pnpm", "start"]
