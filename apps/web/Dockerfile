FROM node:22-alpine
WORKDIR /app
RUN corepack enable
COPY package.json tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN pnpm install --no-frozen-lockfile
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
