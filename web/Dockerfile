# Bússola: imagem do BFF com o front (serviço Cloud Run `bussola-bff`).
#
# O contexto de build é a RAIZ do repositório, porque a varredura do bundle lê
# `contracts/env.example`. O BuildKit usa `web/Dockerfile.dockerignore`.
#
#   docker buildx build --platform linux/amd64 -f web/Dockerfile .
#
# Estágio 1: `npm run build` (tsc, vite e varredura do bundle) com o login do
# BFF ligado e o modo ao vivo como padrão. Estágio 2: só o BFF (Node 24, TS
# nativo e sem dependências de runtime), o `dist/` e as personas.
FROM node:24-slim AS build

WORKDIR /app/web

COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

COPY contracts/env.example /app/contracts/env.example
COPY web/ ./

# Tudo que começa com VITE_ vai para o bundle: nunca segredo aqui.
ENV VITE_BUSSOLA_MODO=ao-vivo \
    VITE_BUSSOLA_LOGIN=TRUE
RUN npm run build


FROM node:24-slim

LABEL org.opencontainers.image.title="bussola-bff"

ENV NODE_ENV=production \
    PORT=8080 \
    STATIC_DIR=/app/web/dist \
    USERS_FIXTURE=/app/web/fixtures/users.json

WORKDIR /app/web

# package.json dá o "type": "module" ao TypeScript nativo do Node.
COPY web/package.json ./
COPY web/bff/ ./bff/
COPY web/fixtures/users.json ./fixtures/users.json
COPY --from=build /app/web/dist ./dist

# Usuário sem privilégios da imagem oficial; o código fica com dono root.
USER node

EXPOSE 8080

CMD ["node", "bff/main/index.ts"]
