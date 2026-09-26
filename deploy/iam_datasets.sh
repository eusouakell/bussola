#!/usr/bin/env bash
# Bússola: Plano B de IAM em nível de dataset para a SA default de compute (FR-023).
# Simulação por padrão (não chama gcloud nem bq). Ver ajuda com --help.
set -euo pipefail

PROJETO="${BUSSOLA_PROJETO:-batalha-time-07-lkbv}"
NUMERO_PROJETO="${BUSSOLA_NUMERO_PROJETO:-1061873050224}"
LOCAL_BQ="${BUSSOLA_LOCAL_BQ:-us-central1}"
SA_ARG="${BUSSOLA_SA_RUNTIME:-}"
APLICAR=0

# dataset:papel (ciclo 000 §3.5 e mestre §16, Plano B).
CONCESSOES="bussola_dados:roles/bigquery.dataViewer
bussola_app:roles/bigquery.dataEditor
bussola_app_dev:roles/bigquery.dataEditor"

uso() {
  cat <<EOF
Uso: deploy/iam_datasets.sh [--sa EMAIL] [--numero-projeto N] [--aplicar]

Concede papéis do BigQuery em nível de DATASET (nunca no projeto) para a SA de
runtime do Cloud Run. Plano B do mestre §16: a SA default de compute.

  bussola_dados                   roles/bigquery.dataViewer
  bussola_app, bussola_app_dev    roles/bigquery.dataEditor

As concessões usam DCL do BigQuery (GRANT ... ON SCHEMA), que é idempotente e
só altera a política do dataset.

Modos:
  (padrão)    simulação: imprime os comandos e o DCL; não chama gcloud nem bq.
  --aplicar   executa com bq, depois de você DIGITAR o nome do projeto
              (${PROJETO}) no terminal. Mudança de IAM: exige confirmação humana.

Opções:
  --sa EMAIL            SA que recebe os papéis. Padrão: SA default de compute,
                        <número do projeto>-compute@developer.gserviceaccount.com.
                        Nome curto (ex.: bussola-runtime) vira
                        <nome>@${PROJETO}.iam.gserviceaccount.com (Plano A).
  --numero-projeto N    número do projeto para derivar a SA default
                        (padrão: ${NUMERO_PROJETO}).
  -h, --help            mostra esta ajuda.

Variáveis: BUSSOLA_PROJETO, BUSSOLA_NUMERO_PROJETO, BUSSOLA_SA_RUNTIME,
BUSSOLA_LOCAL_BQ (padrão us-central1).
EOF
}

erro() {
  echo "ERRO: $*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --sa)
      [ "$#" -ge 2 ] || erro "--sa precisa de um valor"
      SA_ARG="$2"
      shift 2
      ;;
    --sa=*)
      SA_ARG="${1#--sa=}"
      shift
      ;;
    --numero-projeto)
      [ "$#" -ge 2 ] || erro "--numero-projeto precisa de um valor"
      NUMERO_PROJETO="$2"
      shift 2
      ;;
    --numero-projeto=*)
      NUMERO_PROJETO="${1#--numero-projeto=}"
      shift
      ;;
    --aplicar)
      APLICAR=1
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

printf '%s' "${NUMERO_PROJETO}" | grep -Eq '^[0-9]{6,20}$' \
  || erro "número do projeto inválido: '${NUMERO_PROJETO}'"
printf '%s' "${PROJETO}" | grep -Eq '^[a-z][a-z0-9-]{4,28}[a-z0-9]$' \
  || erro "ID de projeto inválido: '${PROJETO}'"

SA_DEFAULT="${NUMERO_PROJETO}-compute@developer.gserviceaccount.com"
case "${SA_ARG}" in
  "") SA="${SA_DEFAULT}" ;;
  *@*) SA="${SA_ARG}" ;;
  *) SA="${SA_ARG}@${PROJETO}.iam.gserviceaccount.com" ;;
esac
printf '%s' "${SA}" | grep -Eq '^[a-z0-9][a-z0-9.-]*@[a-z0-9.-]+\.gserviceaccount\.com$' \
  || erro "e-mail de service account inválido: '${SA}'"

MEMBRO="serviceAccount:${SA}"

dcl_grant() {
  printf 'GRANT `%s` ON SCHEMA `%s.%s` TO "%s"' "$2" "${PROJETO}" "$1" "${MEMBRO}"
}

dcl_revoke() {
  printf 'REVOKE `%s` ON SCHEMA `%s.%s` FROM "%s"' "$2" "${PROJETO}" "$1" "${MEMBRO}"
}

echo "Projeto:  ${PROJETO} (número ${NUMERO_PROJETO})"
echo "SA:       ${SA}"
echo "Escopo:   só datasets; IAM do projeto não é alterado."
echo

if [ "${APLICAR}" -eq 0 ]; then
  echo "SIMULAÇÃO: nada será executado. Comandos equivalentes:"
  echo
  echo "${CONCESSOES}" | while IFS=: read -r dataset papel; do
    echo "# ${dataset}: ${papel}"
    printf "bq query --project_id=%s --location=%s --use_legacy_sql=false \\\\\n" \
      "${PROJETO}" "${LOCAL_BQ}"
    printf "  '%s'\n\n" "$(dcl_grant "${dataset}" "${papel}")"
  done
  echo "Para desfazer (não executado):"
  echo "${CONCESSOES}" | while IFS=: read -r dataset papel; do
    echo "  $(dcl_revoke "${dataset}" "${papel}")"
  done
  echo
  echo "Para aplicar (integrante com BigQuery Admin, após revisar):"
  echo "  deploy/iam_datasets.sh --aplicar"
  exit 0
fi

# ---- Modo --aplicar: mudança real de IAM, com confirmação digitada. ----

command -v bq >/dev/null 2>&1 || erro "bq não encontrado no PATH (Google Cloud SDK)"

if [ "${SA}" = "${SA_DEFAULT}" ] && command -v gcloud >/dev/null 2>&1; then
  NUMERO_REAL="$(gcloud projects describe "${PROJETO}" --format 'value(projectNumber)' 2>/dev/null || true)"
  if [ -z "${NUMERO_REAL}" ]; then
    echo "AVISO: não foi possível conferir o número do projeto com o gcloud." >&2
  elif [ "${NUMERO_REAL}" != "${NUMERO_PROJETO}" ]; then
    erro "o projeto ${PROJETO} tem número ${NUMERO_REAL}, não ${NUMERO_PROJETO}; nada aplicado"
  fi
fi

echo "Serão aplicadas estas concessões:"
echo "${CONCESSOES}" | while IFS=: read -r dataset papel; do
  echo "  ${papel} em ${PROJETO}.${dataset}"
done
echo

printf 'Para confirmar a mudança de IAM, digite o nome do projeto (%s): ' "${PROJETO}"
RESPOSTA=""
if ! read -r RESPOSTA </dev/tty; then
  echo
  erro "sem terminal interativo para confirmar; nada foi aplicado"
fi
[ "${RESPOSTA}" = "${PROJETO}" ] || erro "confirmação não confere; nada foi aplicado"

FALHAS=0
while IFS=: read -r dataset papel; do
  echo "Aplicando ${papel} em ${dataset}..."
  if bq query --project_id="${PROJETO}" --location="${LOCAL_BQ}" --use_legacy_sql=false \
    "$(dcl_grant "${dataset}" "${papel}")" </dev/null; then
    echo "  ok"
  else
    echo "  FALHOU (o dataset existe? rode antes data/scripts/aplicar_ddl.py)" >&2
    FALHAS=$((FALHAS + 1))
  fi
done <<EOF
${CONCESSOES}
EOF

if [ "${FALHAS}" -gt 0 ]; then
  erro "${FALHAS} concessão(ões) falharam"
fi
echo "Concessões aplicadas. Registre em specs/000-fundacao-contratos (decisão Plano A/B)."
