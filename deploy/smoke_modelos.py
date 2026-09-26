"""Smoke de modelos do ciclo 000 (FR-021, research R-17).

Descobre qual Gemini Flash e qual modelo de embedding respondem no projeto:

1. lista os modelos via Vertex AI em cada local;
2. testa ``gemini-3.8-flash``, ``gemini-3.7-flash`` e ``gemini-3.5-flash``
   (e as variantes ``-preview`` listadas), primeiro em ``us-central1`` e
   depois em ``global``;
3. testa os modelos de embedding e mede a dimensão do vetor;
4. se o Vertex não responder, tenta a Gemini API com a chave do segredo
   ``gemini-api-key``, lida pelo ``gcloud`` direto para a memória do processo.
   A chave nunca é impressa nem gravada.

Sem ``--gravar``, só imprime o relatório. Com ``--gravar``, escreve
``specs/000-fundacao-contratos/modelos.md`` e atualiza ``BUSSOLA_MODEL`` e
``EMBEDDING_MODEL`` em ``contracts/env.example`` com os modelos validados.

Uso (credenciais ADC do integrante):

    uv run --project agent python deploy/smoke_modelos.py [--gravar]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = RAIZ / "contracts" / "env.example"
RELATORIO = RAIZ / "specs" / "000-fundacao-contratos" / "modelos.md"

PROJETO_PADRAO = "batalha-time-07-lkbv"
LOCAIS_PADRAO = "us-central1,global"
FLASH_BASES = ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash")
EMBEDDING_ESTATICOS = (
    "gemini-embedding-001",
    "text-embedding-005",
    "text-multilingual-embedding-002",
)
PADRAO_EMBEDDING = re.compile(
    r"^(gemini-embedding-[\w.-]+|text-embedding-[\w.-]+|text-multilingual-embedding-[\w.-]+)$"
)
MAX_EMBEDDINGS_POR_LOCAL = 6
PROMPT_TESTE = "Responda apenas com a palavra: ok"
SEGREDO_GEMINI = "gemini-api-key"
VIA_VERTEX = "vertex"
VIA_GEMINI_API = "gemini-api"


@dataclass
class Tentativa:
    """Resultado de uma chamada de teste a um modelo."""

    tipo: str  # "flash" | "embedding"
    modelo: str
    via: str  # VIA_VERTEX | VIA_GEMINI_API
    local: str  # local do Vertex ou "-" na Gemini API
    ok: bool
    latencia_ms: int | None = None
    dimensao: int | None = None
    detalhe: str = ""


@dataclass
class Listagem:
    """Modelos encontrados na listagem de um local (ou erro da listagem)."""

    via: str
    local: str
    ids: list[str]
    erro: str = ""


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _id_curto(nome: str) -> str:
    """``publishers/google/models/x`` ou ``models/x`` vira ``x``."""
    return nome.rsplit("/", 1)[-1]


def _resumo_erro(exc: BaseException, ocultar: tuple[str, ...] = ()) -> str:
    """Mensagem curta do erro, sem segredos."""
    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    mensagem = getattr(exc, "message", None)
    if code is not None and (status or mensagem):
        texto = f"{code} {status or ''}: {mensagem or ''}"
    else:
        texto = f"{type(exc).__name__}: {exc}"
    for segredo in ocultar:
        if segredo:
            texto = texto.replace(segredo, "***")
    texto = " ".join(texto.split()).replace("|", "/")
    return texto[:160]


def _http_options(timeout_s: int) -> Any:
    from google.genai import types

    # Uma tentativa só: a latência medida é a de uma chamada, sem retries.
    return types.HttpOptions(
        timeout=timeout_s * 1000,
        retry_options=types.HttpRetryOptions(attempts=1),
    )


def cliente_vertex(projeto: str, local: str, timeout_s: int) -> Any:
    from google import genai

    return genai.Client(
        vertexai=True,
        project=projeto,
        location=local,
        http_options=_http_options(timeout_s),
    )


def cliente_gemini_api(chave: str, timeout_s: int) -> Any:
    from google import genai

    return genai.Client(vertexai=False, api_key=chave, http_options=_http_options(timeout_s))


def listar(cliente: Any, via: str, local: str, ocultar: tuple[str, ...] = ()) -> Listagem:
    try:
        ids = sorted({_id_curto(m.name) for m in cliente.models.list() if m.name})
    except Exception as exc:  # o smoke registra qualquer falha
        return Listagem(via, local, [], _resumo_erro(exc, ocultar))
    return Listagem(via, local, ids)


def candidatos_flash(listagem: Listagem) -> list[str]:
    """Bases na ordem 3.8 → 3.7 → 3.5, cada uma seguida das variantes -preview listadas."""
    candidatos: list[str] = []
    for base in FLASH_BASES:
        candidatos.append(base)
        padrao = re.compile(rf"^{re.escape(base)}-preview(-[\w.-]+)?$")
        candidatos.extend(i for i in listagem.ids if padrao.match(i))
    return candidatos


def candidatos_embedding(listagem: Listagem, atual: str) -> list[str]:
    """Modelo atual do env.example primeiro; depois os listados (ou a lista estática)."""
    encontrados = [i for i in listagem.ids if PADRAO_EMBEDDING.match(i)]
    if not encontrados:
        encontrados = list(EMBEDDING_ESTATICOS)
    encontrados.sort(key=lambda i: (not i.startswith("gemini-embedding"), i))
    ordem = [atual] if atual else []
    ordem.extend(i for i in encontrados if i not in ordem)
    return ordem[:MAX_EMBEDDINGS_POR_LOCAL]


def testar_flash(
    cliente: Any, modelo: str, via: str, local: str, ocultar: tuple[str, ...] = ()
) -> Tentativa:
    inicio = time.perf_counter()
    try:
        resposta = cliente.models.generate_content(model=modelo, contents=PROMPT_TESTE)
        latencia = int((time.perf_counter() - inicio) * 1000)
        texto = (resposta.text or "").strip()
    except Exception as exc:
        return Tentativa("flash", modelo, via, local, False, detalhe=_resumo_erro(exc, ocultar))
    if not texto:
        return Tentativa("flash", modelo, via, local, False, latencia, detalhe="resposta vazia")
    return Tentativa("flash", modelo, via, local, True, latencia, detalhe=texto[:40])


def testar_embedding(
    cliente: Any, modelo: str, via: str, local: str, ocultar: tuple[str, ...] = ()
) -> Tentativa:
    inicio = time.perf_counter()
    try:
        resposta = cliente.models.embed_content(model=modelo, contents=PROMPT_TESTE)
        latencia = int((time.perf_counter() - inicio) * 1000)
        valores = resposta.embeddings[0].values if resposta.embeddings else None
    except Exception as exc:
        return Tentativa("embedding", modelo, via, local, False, detalhe=_resumo_erro(exc, ocultar))
    if not valores:
        return Tentativa("embedding", modelo, via, local, False, latencia, detalhe="vetor vazio")
    return Tentativa("embedding", modelo, via, local, True, latencia, dimensao=len(valores))


def _registrar(tentativa: Tentativa) -> Tentativa:
    onde = tentativa.via if tentativa.local == "-" else f"{tentativa.via}/{tentativa.local}"
    if tentativa.ok:
        extra = f", dim {tentativa.dimensao}" if tentativa.dimensao else ""
        _log(f"  ok    {tentativa.modelo} ({onde}) {tentativa.latencia_ms} ms{extra}")
    else:
        _log(f"  falha {tentativa.modelo} ({onde}): {tentativa.detalhe}")
    return tentativa


def ler_chave_gemini(projeto: str) -> tuple[str | None, str]:
    """Lê a chave do Secret Manager direto para a memória. Nunca imprime a chave."""
    comando = [
        "gcloud",
        "secrets",
        "versions",
        "access",
        "latest",
        f"--secret={SEGREDO_GEMINI}",
        f"--project={projeto}",
    ]
    try:
        proc = subprocess.run(comando, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"gcloud indisponível ({type(exc).__name__})"
    if proc.returncode != 0:
        # O stderr de uma falha não contém a chave; mostra só a primeira linha.
        linhas = proc.stderr.strip().splitlines()
        primeira = linhas[0][:160] if linhas else ""
        return None, f"gcloud secrets falhou (código {proc.returncode}): {primeira}"
    chave = proc.stdout.strip()
    if not chave:
        return None, "segredo vazio"
    return chave, ""


def valor_env_example(chave: str) -> str:
    if not ENV_EXAMPLE.exists():
        return ""
    padrao = re.compile(rf"^{re.escape(chave)}=(.*)$", re.MULTILINE)
    achados = padrao.findall(ENV_EXAMPLE.read_text(encoding="utf-8"))
    return achados[-1].strip() if achados else ""


def escolher(tentativas: list[Tentativa], tipo: str) -> Tentativa | None:
    """Primeira tentativa bem-sucedida na ordem de teste (que já é a de preferência)."""
    return next((t for t in tentativas if t.tipo == tipo and t.ok), None)


def _locais(args: argparse.Namespace) -> list[str]:
    return [loc.strip() for loc in args.locais.split(",") if loc.strip()]


def executar(args: argparse.Namespace) -> tuple[list[Listagem], list[Tentativa], list[str]]:
    locais = _locais(args)
    embedding_atual = valor_env_example("EMBEDDING_MODEL")
    listagens: list[Listagem] = []
    tentativas: list[Tentativa] = []
    notas: list[str] = []

    for local in locais:
        _log(f"Vertex AI em {local}:")
        try:
            cliente = cliente_vertex(args.projeto, local, args.timeout)
        except Exception as exc:
            erro = _resumo_erro(exc)
            _log(f"  cliente indisponível: {erro}")
            listagens.append(Listagem(VIA_VERTEX, local, [], erro))
            continue
        listagem = listar(cliente, VIA_VERTEX, local)
        listagens.append(listagem)
        if listagem.erro:
            _log(f"  listagem falhou: {listagem.erro}")
        else:
            _log(f"  {len(listagem.ids)} modelos listados")
        for modelo in candidatos_flash(listagem):
            tentativas.append(_registrar(testar_flash(cliente, modelo, VIA_VERTEX, local)))
        for modelo in candidatos_embedding(listagem, embedding_atual):
            tentativas.append(_registrar(testar_embedding(cliente, modelo, VIA_VERTEX, local)))

    falta_flash = escolher(tentativas, "flash") is None
    falta_embedding = escolher(tentativas, "embedding") is None
    if (falta_flash or falta_embedding) and args.sem_gemini_api:
        notas.append("Fallback pela Gemini API desativado (--sem-gemini-api).")
    elif falta_flash or falta_embedding:
        _log("Gemini API (fallback, chave do Secret Manager em memória):")
        chave, erro = ler_chave_gemini(args.projeto)
        if chave is None:
            _log(f"  chave indisponível: {erro}")
            notas.append(f"Fallback pela Gemini API sem chave: {erro}.")
        else:
            ocultar = (chave,)
            try:
                cliente = cliente_gemini_api(chave, args.timeout)
                listagem = listar(cliente, VIA_GEMINI_API, "-", ocultar)
                listagens.append(listagem)
                if falta_flash:
                    for modelo in candidatos_flash(listagem):
                        t = testar_flash(cliente, modelo, VIA_GEMINI_API, "-", ocultar)
                        tentativas.append(_registrar(t))
                if falta_embedding:
                    for modelo in candidatos_embedding(listagem, embedding_atual):
                        t = testar_embedding(cliente, modelo, VIA_GEMINI_API, "-", ocultar)
                        tentativas.append(_registrar(t))
            except Exception as exc:
                erro = _resumo_erro(exc, ocultar)
                _log(f"  Gemini API indisponível: {erro}")
                notas.append(f"Gemini API indisponível: {erro}.")
            finally:
                del chave, ocultar
    return listagens, tentativas, notas


def _celula(valor: object) -> str:
    return "-" if valor in (None, "") else str(valor)


def montar_relatorio(
    args: argparse.Namespace,
    listagens: list[Listagem],
    tentativas: list[Tentativa],
    notas: list[str],
) -> str:
    flash = escolher(tentativas, "flash")
    embedding = escolher(tentativas, "embedding")
    agora = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    linhas = [
        "# Modelos validados no ciclo 000",
        "",
        "Gerado por `deploy/smoke_modelos.py` (FR-021, research R-17) com as",
        "credenciais ADC de um integrante.",
        "",
        f"- Data: {agora}",
        f"- Projeto: `{args.projeto}`",
        f"- Locais do Vertex testados: {', '.join(f'`{x}`' for x in _locais(args))}",
        "",
        "## Resultado",
        "",
        "| Variável | Modelo | Via | Local | Latência (ms) | Dimensão |",
        "|---|---|---|---|---|---|",
    ]
    for nome, escolhido in (("BUSSOLA_MODEL", flash), ("EMBEDDING_MODEL", embedding)):
        if escolhido is None:
            linhas.append(f"| `{nome}` | **nenhum respondeu** | - | - | - | - |")
        else:
            linhas.append(
                f"| `{nome}` | `{escolhido.modelo}` | {escolhido.via} | {escolhido.local} "
                f"| {_celula(escolhido.latencia_ms)} | {_celula(escolhido.dimensao)} |"
            )

    linhas += ["", "## Implicações", ""]
    if flash is None:
        linhas.append("- Nenhum Gemini Flash respondeu: acionar Plano B (mestre §16).")
    elif flash.via == VIA_GEMINI_API:
        linhas.append(
            "- O Flash só respondeu pela Gemini API: Plano B de LLM "
            "(`GOOGLE_GENAI_USE_VERTEXAI=FALSE`, `deploy/deploy.sh agent --llm gemini-api`)."
        )
    elif flash.local != "us-central1":
        linhas.append(
            f"- O Flash só respondeu em `{flash.local}`: no deploy do agente use "
            f"`BUSSOLA_LOCAL_MODELO={flash.local}`."
        )
    else:
        linhas.append("- Plano A de LLM viável com as credenciais do integrante (Vertex AI).")
    if embedding is not None:
        linhas.append(
            f"- Dimensão do embedding `{embedding.modelo}`: {embedding.dimensao} "
            "(conferir com o DDL de `bussola_rag`)."
        )
    linhas.append(
        "- Este teste usa as credenciais do integrante. A SA de runtime do Cloud Run "
        "pode não ter o mesmo acesso (ver o deploy hello)."
    )
    linhas += [f"- {nota}" for nota in notas]

    linhas += ["", "## Listagem de modelos", ""]
    for listagem in listagens:
        onde = listagem.via if listagem.local == "-" else f"{listagem.via} / `{listagem.local}`"
        if listagem.erro:
            linhas.append(f"- {onde}: listagem falhou ({listagem.erro}); usados candidatos fixos.")
            continue
        flashs = [i for i in listagem.ids if any(i.startswith(b) for b in FLASH_BASES)]
        embeds = [i for i in listagem.ids if PADRAO_EMBEDDING.match(i)]
        linhas.append(
            f"- {onde}: {len(listagem.ids)} modelos. Flash listados: "
            f"{', '.join(f'`{i}`' for i in flashs) or 'nenhum'}. Embeddings: "
            f"{', '.join(f'`{i}`' for i in embeds) or 'nenhum'}."
        )

    linhas += [
        "",
        "## Tentativas",
        "",
        "| Tipo | Modelo | Via | Local | Resultado | Latência (ms) | Dimensão | Detalhe |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t in tentativas:
        resultado = "ok" if t.ok else "falha"
        linhas.append(
            f"| {t.tipo} | `{t.modelo}` | {t.via} | {t.local} | {resultado} "
            f"| {_celula(t.latencia_ms)} | {_celula(t.dimensao)} | {_celula(t.detalhe)} |"
        )
    linhas.append("")
    return "\n".join(linhas)


def atualizar_env_example(flash: Tentativa | None, embedding: Tentativa | None) -> list[str]:
    """Troca só as linhas BUSSOLA_MODEL e EMBEDDING_MODEL. Devolve o que mudou."""
    texto = ENV_EXAMPLE.read_text(encoding="utf-8")
    mudancas: list[str] = []
    for chave, escolhido in (("BUSSOLA_MODEL", flash), ("EMBEDDING_MODEL", embedding)):
        if escolhido is None:
            continue
        padrao = re.compile(rf"^{chave}=.*$", re.MULTILINE)
        if not padrao.search(texto):
            _log(f"AVISO: {chave} não encontrado em {ENV_EXAMPLE}; linha não alterada.")
            continue
        novo = padrao.sub(f"{chave}={escolhido.modelo}", texto)
        if novo != texto:
            mudancas.append(f"{chave}={escolhido.modelo}")
            texto = novo
    if mudancas:
        ENV_EXAMPLE.write_text(texto, encoding="utf-8")
    return mudancas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Valida o Gemini Flash (3.8 → 3.7 → 3.5) e o modelo de embedding via Vertex AI, "
            "com fallback pela Gemini API. Sem --gravar, só imprime o relatório."
        ),
    )
    parser.add_argument(
        "--projeto",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT") or PROJETO_PADRAO,
        help="projeto GCP (padrão: GOOGLE_CLOUD_PROJECT ou %(default)s)",
    )
    parser.add_argument(
        "--locais",
        default=LOCAIS_PADRAO,
        help="locais do Vertex, em ordem de preferência (padrão: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="timeout de cada chamada, em segundos (padrão: %(default)s)",
    )
    parser.add_argument(
        "--sem-gemini-api",
        action="store_true",
        help="não tenta o fallback pela Gemini API (não lê o segredo gemini-api-key)",
    )
    parser.add_argument(
        "--gravar",
        action="store_true",
        help=(
            "grava specs/000-fundacao-contratos/modelos.md e atualiza BUSSOLA_MODEL e "
            "EMBEDDING_MODEL em contracts/env.example (só integrante, após revisar)"
        ),
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout deve ser positivo")
    if not _locais(args):
        parser.error("--locais vazio")

    listagens, tentativas, notas = executar(args)
    relatorio = montar_relatorio(args, listagens, tentativas, notas)
    print(relatorio)

    flash = escolher(tentativas, "flash")
    embedding = escolher(tentativas, "embedding")
    if args.gravar:
        RELATORIO.parent.mkdir(parents=True, exist_ok=True)
        RELATORIO.write_text(relatorio, encoding="utf-8")
        _log(f"Relatório gravado em {RELATORIO.relative_to(RAIZ)}")
        mudancas = atualizar_env_example(flash, embedding)
        if mudancas:
            _log(f"contracts/env.example atualizado: {', '.join(mudancas)}")
        else:
            _log("contracts/env.example sem mudanças.")
    else:
        _log("Modo leitura: nada gravado (use --gravar para gravar modelos.md e env.example).")

    return 0 if flash is not None and embedding is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
