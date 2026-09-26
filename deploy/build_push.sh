#!/usr/bin/env bash
# Bússola: build linux/amd64 e push de uma imagem para o Artifact Registry.
# Ver ajuda com --help. Não faz deploy, não mexe em IAM nem em tráfego.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PROJETO="${BUSSOLA_PROJETO:-batalha-time-07-lkbv}"
REGIAO="${BUSSOLA_REGIAO:-us-central1}"
AR_REPO="${BUSSOLA_AR_REPO:-agentes}"
AR_HOST="${REGIAO}-docker.pkg.dev"

uso() {
  cat <<EOF
Uso: deploy/build_push.sh <mcp|agent> [tag]

Faz o build da imagem para linux/amd64 com docker buildx (contexto = raiz do
repositório) e publica no Artifact Registry:

  ${AR_HOST}/${PROJETO}/${AR_REPO}/<serviço>:<tag>

Serviços:
  mcp    (ou bussola-mcp)    usa mcp_server/Dockerfile -> imagem bussola-mcp
  agent  (ou bussola-agent)  usa agent/Dockerfile      -> imagem bussola-agent

Tag: padrão = SHA curto do commit atual (com sufixo -dirty se houver mudanças
não commitadas). Pode ser qualquer tag Docker válida, por exemplo c000.

Variáveis (com padrão):
  BUSSOLA_PROJETO  projeto GCP              (batalha-time-07-lkbv)
  BUSSOLA_REGIAO   região do Artifact Reg.  (us-central1)
  BUSSOLA_AR_REPO  repositório Docker       (agentes)

Pré-requisitos: docker com buildx e credencial do Artifact Registry, criada uma
vez com:
  gcloud auth configure-docker ${AR_HOST}
EOF
}

erro() {
  echo "ERRO: $*" >&2
  exit 1
}

aviso() {
  echo "AVISO: $*" >&2
}

case "${1:-}" in
  -h | --help)
    uso
    exit 0
    ;;
  mcp | bussola-mcp)
    SERVICO="bussola-mcp"
    DOCKERFILE="${RAIZ}/mcp_server/Dockerfile"
    ;;
  agent | bussola-agent)
    SERVICO="bussola-agent"
    DOCKERFILE="${RAIZ}/agent/Dockerfile"
    ;;
  "")
    uso >&2
    exit 2
    ;;
  *)
    erro "serviço desconhecido: '$1' (use mcp ou agent; veja --help)"
    ;;
esac

if [ "$#" -gt 2 ]; then
  erro "argumentos demais (veja --help)"
fi

[ -f "${DOCKERFILE}" ] || erro "Dockerfile não encontrado: ${DOCKERFILE}"

REVISAO="$(git -C "${RAIZ}" rev-parse --short HEAD 2>/dev/null || echo desconhecida)"

if [ "$#" -ge 2 ] && [ -n "$2" ]; then
  TAG="$2"
else
  [ "${REVISAO}" != "desconhecida" ] || erro "sem commit git para gerar a tag; informe a tag"
  TAG="${REVISAO}"
  if [ -n "$(git -C "${RAIZ}" status --porcelain 2>/dev/null)" ]; then
    TAG="${TAG}-dirty"
    aviso "há mudanças não commitadas; a tag será ${TAG}"
  fi
fi

if ! printf '%s' "${TAG}" | grep -Eq '^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$'; then
  erro "tag Docker inválida: '${TAG}'"
fi

command -v docker >/dev/null 2>&1 || erro "docker não encontrado no PATH"
docker buildx version >/dev/null 2>&1 || erro "docker buildx não disponível"

CONFIG_DOCKER="${DOCKER_CONFIG:-${HOME}/.docker}/config.json"
if [ ! -f "${CONFIG_DOCKER}" ] || ! grep -q "${AR_HOST}" "${CONFIG_DOCKER}"; then
  aviso "credencial do ${AR_HOST} não encontrada em ${CONFIG_DOCKER}."
  aviso "se o push falhar, rode uma vez: gcloud auth configure-docker ${AR_HOST}"
fi

IMAGEM="${AR_HOST}/${PROJETO}/${AR_REPO}/${SERVICO}:${TAG}"

echo "Serviço:    ${SERVICO}"
echo "Dockerfile: ${DOCKERFILE#"${RAIZ}"/}"
echo "Imagem:     ${IMAGEM}"
echo "Build linux/amd64 e push..."

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --file "${DOCKERFILE}" \
  --label "org.opencontainers.image.revision=${REVISAO}" \
  --tag "${IMAGEM}" \
  --push \
  "${RAIZ}"

echo "Imagem publicada: ${IMAGEM}"
echo "Próximo passo: deploy/deploy.sh ${SERVICO#bussola-} --imagem ${TAG}"
