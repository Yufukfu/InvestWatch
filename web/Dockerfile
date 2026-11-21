# syntax=docker/dockerfile:1
# Official images via the AWS ECR mirror of Docker Hub (avoids anonymous pull rate limits).

FROM public.ecr.aws/docker/library/node:22-alpine AS build
WORKDIR /app
ENV CI=true
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Contract snapshot (src/api/openapi.json, generated.ts) is committed, so the image builds without ../contracts.
# `build` runs tsc -b itself, so no separate typecheck step.
RUN npm run lint && npx vitest run src && npm run build

FROM public.ecr.aws/nginx/nginx-unprivileged:1.29-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
