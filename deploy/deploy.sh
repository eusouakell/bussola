#!/usr/bin/env bash
# Bússola: deploy de uma imagem já publicada no Cloud Run (research R-18).
# Ver ajuda com --help. Nunca move tráfego de serviço existente e nunca mexe em IAM.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_EXAMPLE="${RAIZ}/contracts/env.example"

PROJETO="${BUSSOLA_PROJETO:-batalha-time-07-lkbv}"
NUMERO_PROJETO="${BUSSOLA_NUMERO_PROJETO:-1061873050224}"
REGIAO="${BUSSOLA_REGIAO:-us-central1}"
AR_REPO="${BUSSOLA_AR_REPO:-agentes}"
MAX_INSTANCIAS="${BUSSOLA_MAX_INSTANCIAS:-1}"

uso() {
  cat <<EOF
Uso: deploy/deploy.sh <mcp|agent> [--tag cNNN] [--no-traffic] [--imagem TAG|URI]
                      [--llm vertex|gemini-api]

Publica uma revisão no Cloud Run (projeto ${PROJETO}, região ${REGIAO}) a
partir de uma imagem já enviada por deploy/build_push.sh.

Regras (constituição X e R-18):
  - Serviço já existe: a revisão nova sai com --tag <cNNN> --no-traffic e não
    recebe tráfego. Mover tráfego é do ciclo 007, com confirmação humana.
  - Serviço ainda não existe: o gcloud não aceita --no-traffic na criação; a
    primeira revisão recebe 100% do tráfego do serviço novo e privado
    (--no-allow-unauthenticated).
  - IAM: --no-allow-unauthenticated só é passado na criação. Em atualização o
    script não passa nenhuma opção de acesso, para não tocar na política IAM.
  - Segredos só por --set-secrets (Secret Manager), nunca por valor.

Opções:
  --tag cNNN       tag da revisão (padrão: c000). Formato: c + 3 dígitos,
                   com sufixos opcionais em minúsculas (ex.: c000-hello).
  --no-traffic     aceito por compatibilidade; em atualização já é sempre usado.
  --imagem X       tag da imagem no Artifact Registry ou URI completo
                   (padrão: SHA curto do commit atual, igual ao build_push.sh).
  --llm MODO       só para agent. vertex (padrão, Plano A) ou gemini-api
                   (Plano B: GOOGLE_GENAI_USE_VERTEXAI=FALSE e GOOGLE_API_KEY
                   vindo do segredo gemini-api-key via --set-secrets).
  -h, --help       mostra esta ajuda.

Serviços:
  mcp    (ou bussola-mcp)    mock MCP com BUSSOLA_FAKES=TRUE
  agent  (ou bussola-agent)  agente ADK; MCP_URL = URL do bussola-mcp + /mcp
                             e MCP_USE_OIDC=TRUE (fazer o deploy do mcp antes)

Variáveis (com padrão):
  BUSSOLA_PROJETO         projeto GCP                  (batalha-time-07-lkbv)
  BUSSOLA_NUMERO_PROJETO  número do projeto            (1061873050224)
  BUSSOLA_REGIAO          região do Cloud Run          (us-central1)
  BUSSOLA_AR_REPO         repositório Docker           (agentes)
  BUSSOLA_SA_RUNTIME      SA de runtime dos 2 serviços (Plano B: SA default de
                          compute <número>-compute@developer.gserviceaccount.com).
                          Plano A (mestre §16): BUSSOLA_SA_RUNTIME=bussola-runtime
                          (nome curto vira bussola-runtime@<projeto>.iam...).
  BUSSOLA_SA_MCP / BUSSOLA_SA_AGENTE  SA específica de um serviço (opcional).
  BUSSOLA_LOCAL_MODELO    GOOGLE_CLOUD_LOCATION do agente (padrão: env.example,
                          global; Q-15 do 000). Sem valor, usa GOOGLE_CLOUD_LOCATION.
  BUSSOLA_MCP_URL         MCP_URL explícita (padrão: consulta o bussola-mcp).
  BUSSOLA_FAKES           TRUE no ciclo 000.
  BUSSOLA_MAX_INSTANCIAS  máximo de instâncias (1; mestre §13).
  BUSSOLA_MEMORIA_MCP / BUSSOLA_MEMORIA_AGENTE  memória (512Mi / 1Gi).
  BUSSOLA_MODEL, EMBEDDING_MODEL, ANCHOR_USER_ID, REPLAY_START_ANOMES,
  MODEL_ARMOR_TEMPLATE, LOG_LEVEL: sobrepõem os valores de contracts/env.example.
EOF
}

erro() {
  echo "ERRO: $*" >&2
  exit 1
}

aviso() {
  echo "AVISO: $*" >&2
}

# Valor de uma chave de contracts/env.example (vazio se não existir).
valor_contrato() {
  [ -f "${ENV_EXAMPLE}" ] || return 0
  sed -n "s/^$1=//p" "${ENV_EXAMPLE}" | tail -n 1
}

# Valor da variável de ambiente de mesmo nome ou, na falta, do env.example.
valor() {
  local atual
  atual="$(printenv "$1" 2>/dev/null || true)"
  if [ -n "${atual}" ]; then
    printf '%s' "${atual}"
  else
    valor_contrato "$1"
  fi
}

# Nome curto de SA (sem @) vira e-mail de SA do projeto.
email_sa() {
  case "$1" in
    *@*) printf '%s' "$1" ;;
    *) printf '%s@%s.iam.gserviceaccount.com' "$1" "${PROJETO}" ;;
  esac
}

case "${1:-}" in
  -h | --help)
    uso
    exit 0
    ;;
  mcp | bussola-mcp)
    ALVO="mcp"
    SERVICO="bussola-mcp"
    ;;
  agent | bussola-agent)
    ALVO="agent"
    SERVICO="bussola-agent"
    ;;
  "")
    uso >&2
    exit 2
    ;;
  *)
    erro "serviço desconhecido: '$1' (use mcp ou agent; veja --help)"
    ;;
esac
shift

TAG_REVISAO="c000"
IMAGEM_ARG=""
LLM="vertex"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --tag)
      [ "$#" -ge 2 ] || erro "--tag precisa de um valor"
      TAG_REVISAO="$2"
      shift 2
      ;;
    --tag=*)
      TAG_REVISAO="${1#--tag=}"
      shift
      ;;
    --no-traffic)
      shift
      ;;
    --imagem)
      [ "$#" -ge 2 ] || erro "--imagem precisa de um valor"
      IMAGEM_ARG="$2"
      shift 2
      ;;
    --imagem=*)
      IMAGEM_ARG="${1#--imagem=}"
      shift
      ;;
    --llm)
      [ "$#" -ge 2 ] || erro "--llm precisa de um valor"
      LLM="$2"
      shift 2
      ;;
    --llm=*)
      LLM="${1#--llm=}"
      shift
      ;;
    -h | --help)
      uso
      exit 0
      ;;
    *)
      erro "opção desconhecida: '$1' (veja --help)"
      ;;
  esac
done

if ! printf '%s' "${TAG_REVISAO}" | grep -Eq '^c[0-9]{3}(-[a-z0-9]+)*$'; then
  erro "tag de revisão inválida: '${TAG_REVISAO}' (esperado cNNN, ex.: c000)"
fi

case "${LLM}" in
  vertex | gemini-api) ;;
  *) erro "--llm inválido: '${LLM}' (use vertex ou gemini-api)" ;;
esac
if [ "${ALVO}" = "mcp" ] && [ "${LLM}" != "vertex" ]; then
  erro "--llm só se aplica ao agent"
fi

# Imagem: URI completo, tag explícita ou SHA curto (mesma regra do build_push.sh).
AR_HOST="${REGIAO}-docker.pkg.dev"
case "${IMAGEM_ARG}" in
  */*)
    IMAGEM="${IMAGEM_ARG}"
    ;;
  "")
    SHA="$(git -C "${RAIZ}" rev-parse --short HEAD 2>/dev/null)" \
      || erro "sem commit git para deduzir a imagem; use --imagem"
    if [ -n "$(git -C "${RAIZ}" status --porcelain 2>/dev/null)" ]; then
      SHA="${SHA}-dirty"
    fi
    IMAGEM="${AR_HOST}/${PROJETO}/${AR_REPO}/${SERVICO}:${SHA}"
    ;;
  *)
    IMAGEM="${AR_HOST}/${PROJETO}/${AR_REPO}/${SERVICO}:${IMAGEM_ARG}"
    ;;
esac

# SA de runtime: Plano B (padrão) = SA default de compute; Plano A = bussola-runtime.
SA_PADRAO="${BUSSOLA_SA_RUNTIME:-${NUMERO_PROJETO}-compute@developer.gserviceaccount.com}"
if [ "${ALVO}" = "mcp" ]; then
  SA="$(email_sa "${BUSSOLA_SA_MCP:-${SA_PADRAO}}")"
  MEMORIA="${BUSSOLA_MEMORIA_MCP:-512Mi}"
else
  SA="$(email_sa "${BUSSOLA_SA_AGENTE:-${SA_PADRAO}}")"
  MEMORIA="${BUSSOLA_MEMORIA_AGENTE:-1Gi}"
fi

command -v gcloud >/dev/null 2>&1 || erro "gcloud não encontrado no PATH"

ERR_TMP="$(mktemp)"
trap 'rm -f "${ERR_TMP}"' EXIT

# Consulta o serviço no shell atual (sem subshell, para o erro abortar o script).
# Retorna 0 se existe (URL em URL_SERVICO) e 1 se não existe. Qualquer outro
# erro (credencial, permissão, rede) aborta.
URL_SERVICO=""
consultar_servico() {
  URL_SERVICO=""
  if URL_SERVICO="$(gcloud run services describe "$1" \
    --project "${PROJETO}" --region "${REGIAO}" \
    --format 'value(status.url)' 2>"${ERR_TMP}")"; then
    return 0
  fi
  URL_SERVICO=""
  if grep -Eqi 'cannot find service|not_found|could not be found' "${ERR_TMP}"; then
    return 1
  fi
  cat "${ERR_TMP}" >&2
  erro "não foi possível consultar o serviço $1 (credenciais? permissão?)"
}

LOCAL_GCP="$(valor_contrato GOOGLE_CLOUD_LOCATION)"
LOCAL_GCP="${LOCAL_GCP:-us-central1}"
FAKES="${BUSSOLA_FAKES:-TRUE}"
NIVEL_LOG="$(valor LOG_LEVEL)"
NIVEL_LOG="${NIVEL_LOG:-INFO}"

ENVS=("GOOGLE_CLOUD_PROJECT=${PROJETO}")
SEGREDOS=""

if [ "${ALVO}" = "mcp" ]; then
  ENVS+=(
    "GOOGLE_CLOUD_LOCATION=${LOCAL_GCP}"
    "EMBEDDING_MODEL=$(valor EMBEDDING_MODEL)"
    "BQ_DATASET_DADOS=$(valor_contrato BQ_DATASET_DADOS)"
    "BQ_DATASET_RAG=$(valor_contrato BQ_DATASET_RAG)"
    "BQ_MODO_LEITURA=$(valor_contrato BQ_MODO_LEITURA)"
    "RAG_BACKEND=$(valor_contrato RAG_BACKEND)"
  )
else
  if [ -n "${BUSSOLA_MCP_URL:-}" ]; then
    MCP_URL="${BUSSOLA_MCP_URL}"
  else
    consultar_servico bussola-mcp \
      || erro "bussola-mcp não existe; faça antes: deploy/deploy.sh mcp"
    [ -n "${URL_SERVICO}" ] || erro "bussola-mcp sem URL; defina BUSSOLA_MCP_URL"
    MCP_URL="${URL_SERVICO%/}/mcp"
  fi

  if [ "${LLM}" = "gemini-api" ]; then
    USA_VERTEX="FALSE"
    SEGREDOS="GOOGLE_API_KEY=gemini-api-key:latest"
    aviso "Plano B: a SA de runtime precisa de secretAccessor em gemini-api-key."
  else
    USA_VERTEX="TRUE"
  fi

  LOCAL_MODELO="$(valor BUSSOLA_LOCAL_MODELO)"
  LOCAL_MODELO="${LOCAL_MODELO:-${LOCAL_GCP}}"

  ENVS+=(
    "GOOGLE_CLOUD_LOCATION=${LOCAL_MODELO}"
    "GOOGLE_GENAI_USE_VERTEXAI=${USA_VERTEX}"
    "BUSSOLA_MODEL=$(valor BUSSOLA_MODEL)"
    "MCP_URL=${MCP_URL}"
    "MCP_USE_OIDC=TRUE"
    "ANCHOR_USER_ID=$(valor ANCHOR_USER_ID)"
    "REPLAY_START_ANOMES=$(valor REPLAY_START_ANOMES)"
    "BQ_DATASET_APP=$(valor_contrato BQ_DATASET_APP)"
  )
  ARMOR="$(valor MODEL_ARMOR_TEMPLATE)"
  if [ -n "${ARMOR}" ]; then
    ENVS+=("MODEL_ARMOR_TEMPLATE=${ARMOR}")
  fi
fi

ENVS+=("BUSSOLA_FAKES=${FAKES}" "LOG_LEVEL=${NIVEL_LOG}")

# Junta as variáveis com vírgula; nenhuma pode vir vazia nem conter vírgula.
LISTA_ENVS=""
for par in "${ENVS[@]}"; do
  case "${par}" in
    *=) erro "variável sem valor: ${par} (confira contracts/env.example)" ;;
    *,*) erro "valor com vírgula não suportado: ${par%%=*}" ;;
  esac
  LISTA_ENVS="${LISTA_ENVS:+${LISTA_ENVS},}${par}"
done

CMD=(
  gcloud run deploy "${SERVICO}"
  --project "${PROJETO}"
  --region "${REGIAO}"
  --image "${IMAGEM}"
  --service-account "${SA}"
  --port 8080
  --memory "${MEMORIA}"
  --cpu 1
  --max-instances "${MAX_INSTANCIAS}"
  --set-env-vars "${LISTA_ENVS}"
  --tag "${TAG_REVISAO}"
)

if [ -n "${SEGREDOS}" ]; then
  CMD+=(--set-secrets "${SEGREDOS}")
fi

if consultar_servico "${SERVICO}"; then
  echo "Serviço ${SERVICO} existe: revisão nova com tag ${TAG_REVISAO}, sem tráfego."
  CMD+=(--no-traffic)
  if [ -z "${SEGREDOS}" ]; then
    # Revisão determinística: não herda segredo de uma revisão anterior (Plano B).
    CMD+=(--clear-secrets)
  fi
else
  echo "Serviço ${SERVICO} não existe: criação privada (--no-allow-unauthenticated)."
  echo "A primeira revisão recebe 100% do tráfego do serviço novo (o gcloud não"
  echo "aceita --no-traffic na criação)."
  CMD+=(--no-allow-unauthenticated)
fi

echo "SA de runtime: ${SA}"
echo "Comando:"
printf '  %q' "${CMD[@]}"
printf '\n'

"${CMD[@]}"

echo
echo "Deploy concluído. URL da revisão (tag ${TAG_REVISAO}):"
echo "  gcloud run services describe ${SERVICO} --project ${PROJETO} --region ${REGIAO} \\"
echo "    --format 'value(status.traffic)'"
echo "Teste privado (ID token do integrante):"
echo "  curl -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" <URL>"
