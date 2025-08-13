# ----------- Base Stage -----------
FROM node:20-slim AS base
WORKDIR /app
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@10.14.0 --activate
COPY package.json pnpm-lock.yaml ./
COPY .env ./
RUN pnpm install --frozen-lockfile

# ----------- Development Stage -----------
FROM base AS dev
COPY . .
EXPOSE 5173
ENV NODE_ENV=development
CMD ["pnpm", "dev", "--host"]

# ----------- Build Stage -----------
FROM base AS build
COPY . .
RUN pnpm build

# ----------- Production Stage -----------
FROM node:20-slim AS prod
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY package.json ./
COPY pnpm-lock.yaml ./
COPY .env.prod ./
RUN corepack enable && corepack prepare pnpm@10.14.0 --activate && pnpm install --prod --frozen-lockfile
EXPOSE 80
ENV NODE_ENV=production
CMD ["pnpm", "serve"]
