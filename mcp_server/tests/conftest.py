"""Configuração comum dos testes do MCP server.

- ``BUSSOLA_FAKES=TRUE`` por padrão (os testes nunca usam BigQuery real).
- Guarda de rede: só loopback e sockets Unix, exceto nos testes marcados ``bq``.
- ``fixtures_sinteticas``: conjunto mínimo de fixtures **sintéticas** em
  ``tmp_path``, válido pelos modelos de ``contratos.py``. Os valores são
  inventados para teste e não representam os dados oficiais (contratos §8).
"""

import ipaddress
import json
import os
import socket
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

os.environ.setdefault("BUSSOLA_FAKES", "TRUE")

from bussola_mcp.contratos import (  # noqa: E402
    CORTES_GOLDEN,
    ENTRADA_CANONICA_SIMULACAO,
    FERRAMENTAS_GOLDEN,
    ID_ANCORA,
    ID_CONTROLE,
    TABELAS_FERRAMENTA,
    Categoria,
    Cenario,
    CorteSugerido,
    DadosCapacidadePoupanca,
    DadosCompararCenarios,
    DadosDividasParcelas,
    DadosOportunidadesCorte,
    DadosPerfilFinanceiro,
    DadosResumoMes,
    DadosSimularObjetivo,
    EntradaCategoria,
    Fonte,
    FonteRenda,
    FonteTrecho,
    GastoCategoria,
    GastoMacro,
    Oportunidade,
    Parcela,
    ParcelaAtiva,
    PerfilMes,
    Periodo,
    PontoMensal,
    Recorrente,
    RefCoorte,
    RegrasCenario,
    Resposta,
    Saldo,
    TemaConhecimento,
    TrechoCorpus,
    UsuarioFixture,
    arquivo_golden,
    arquivo_resumo_mes,
)

# ---------------------------------------------------------------------------
# Guarda de rede
# ---------------------------------------------------------------------------


class RedeBloqueadaError(RuntimeError):
    """Tentativa de acesso à rede fora de loopback durante um teste."""


def _host_loopback(host: Any) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    host = str(host).strip().strip("[]").split("%")[0].lower()
    if host in ("", "localhost") or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.is_loopback:
        return True
    return isinstance(ip, ipaddress.IPv6Address) and bool(
        ip.ipv4_mapped and ip.ipv4_mapped.is_loopback
    )


def _endereco_permitido(sock: socket.socket, endereco: Any) -> bool:
    if sock.family == getattr(socket, "AF_UNIX", object()):
        return True
    if isinstance(endereco, tuple) and endereco:
        return _host_loopback(endereco[0])
    return False


@pytest.fixture(autouse=True)
def _guarda_de_rede(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Bloqueia conexões fora de loopback, salvo nos testes marcados ``bq``."""
    if request.node.get_closest_marker("bq") is not None:
        yield
        return

    connect_original = socket.socket.connect
    connect_ex_original = socket.socket.connect_ex
    getaddrinfo_original = socket.getaddrinfo

    def connect(sock: socket.socket, endereco: Any, *args: Any, **kwargs: Any) -> Any:
        if not _endereco_permitido(sock, endereco):
            raise RedeBloqueadaError("teste tentou acessar a rede fora de loopback")
        return connect_original(sock, endereco, *args, **kwargs)

    def connect_ex(sock: socket.socket, endereco: Any, *args: Any, **kwargs: Any) -> Any:
        if not _endereco_permitido(sock, endereco):
            raise RedeBloqueadaError("teste tentou acessar a rede fora de loopback")
        return connect_ex_original(sock, endereco, *args, **kwargs)

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if not _host_loopback(host):
            raise RedeBloqueadaError("teste tentou resolver um host fora de loopback")
        return getaddrinfo_original(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield


# ---------------------------------------------------------------------------
# Fixtures sintéticas
# ---------------------------------------------------------------------------

MESES = tuple(range(202501, 202513))
MESES_RESUMO_SINTETICO = tuple(range(202501, 202507))  # 202507+ ausente de propósito
FAIXAS = {ID_ANCORA: "6k_10k", ID_CONTROLE: "3k_6k"}
QTD_ITENS_GOLDEN = 10  # máximo de itens do golden de oportunidades (research R-10)


def _dump(item: BaseModel | list[BaseModel]) -> Any:
    if isinstance(item, list):
        return [linha.model_dump(mode="json") for linha in item]
    return item.model_dump(mode="json")


def _gravar(caminho: Path, conteudo: Any) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")


def _base(id_usuario: str) -> float:
    """Renda-base sintética: o controle tem valores diferentes do âncora."""
    return 5000.0 if id_usuario == ID_ANCORA else 3000.0


def _tabelas() -> dict[str, list[BaseModel]]:
    tabelas: dict[str, list[BaseModel]] = {
        "perfil_mensal": [],
        "gastos_categoria": [],
        "entradas_categoria": [],
        "recorrentes": [],
        "parcelas": [],
    }
    for id_usuario in (ID_ANCORA, ID_CONTROLE):
        base = _base(id_usuario)
        for i, anomes in enumerate(MESES):
            renda = base + 10.0 * i
            gasto = base * 0.6
            tabelas["perfil_mensal"].append(
                PerfilMes(
                    id_usuario=id_usuario,
                    anomes=anomes,
                    renda=renda,
                    gasto=gasto,
                    sobra=round(renda - gasto, 2),
                    saldo_inicial=100.0 * i,
                    saldo_final=100.0 * (i + 1),
                    saldo_minimo=-50.0,
                    saldo_maximo=1000.0 + i,
                    juros=5.0,
                )
            )
            for macro, micro, fator in (
                ("Moradia", "Aluguel", 0.3),
                ("Lazer", "Restaurantes", 0.1),
            ):
                tabelas["gastos_categoria"].append(
                    GastoCategoria(
                        id_usuario=id_usuario,
                        anomes=anomes,
                        macro=macro,
                        micro=micro,
                        total=round(base * fator, 2),
                        qtd=2,
                    )
                )
            tabelas["entradas_categoria"].append(
                EntradaCategoria(
                    id_usuario=id_usuario,
                    anomes=anomes,
                    macro="Renda",
                    micro="Salario",
                    total=renda,
                    qtd=1,
                )
            )
            tabelas["recorrentes"].append(
                Recorrente(
                    id_usuario=id_usuario,
                    anomes=anomes,
                    descr_norm="streaming exemplo",
                    macro="Lazer",
                    micro="Assinaturas",
                    valor=39.9,
                )
            )
            tabelas["parcelas"].append(
                Parcela(
                    id_usuario=id_usuario,
                    anomes=anomes,
                    descr="compra parcelada exemplo",
                    macro="Compras",
                    parcela_atual=i + 1,
                    parcela_total=12,
                    vlr=100.0,
                )
            )
    tabelas["categorias"] = [
        Categoria(macro="Moradia", micro="Aluguel", discricionaria=False, corte_max_pct=0.0),
        Categoria(macro="Lazer", micro="Restaurantes", discricionaria=True, corte_max_pct=0.3),
    ]
    tabelas["referencia_coorte"] = [
        RefCoorte(faixa_renda=faixa, macro=macro, media=media, mediana=media, qtd_usuarios=10)
        for faixa in ("6k_10k", "3k_6k")
        for macro, media in (("Moradia", 1500.0), ("Lazer", 400.0))
    ]
    return tabelas


def _trecho(doc_id: str, tema: TemaConhecimento, titulo: str, texto: str) -> TrechoCorpus:
    return TrechoCorpus(
        doc_id=doc_id,
        trecho_id=f"{doc_id}#1",
        titulo=titulo,
        tema=tema,
        texto=texto,
        fonte=FonteTrecho(nome="Fonte sintética", referencia=f"Norma {doc_id}"),
    )


def trechos_sinteticos() -> list[TrechoCorpus]:
    """Corpus de conhecimento sintético: um ou dois trechos por tema (Q-17)."""
    return [
        _trecho(
            "rotativo",
            TemaConhecimento.NORMA_BACEN,
            "Rotativo do cartão",
            "O rotativo do cartão vale só até a fatura seguinte.",
        ),
        _trecho(
            "teto-juros",
            TemaConhecimento.NORMA_BACEN,
            "Teto de juros",
            "Juros do rotativo do cartão limitados ao valor da dívida.",
        ),
        _trecho(
            "cet",
            TemaConhecimento.NORMA_BACEN,
            "Custo Efetivo Total",
            "O CET soma juros, tarifas e seguros.",
        ),
        _trecho(
            "registrato",
            TemaConhecimento.CREDITO,
            "Registrato",
            "Consulte as dívidas em seu nome no Registrato.",
        ),
        _trecho(
            "reserva",
            TemaConhecimento.BOAS_PRATICAS,
            "Reserva de emergência",
            "Guarde de três a seis meses do custo de vida.",
        ),
        TrechoCorpus(
            doc_id="reserva_objetivo",
            trecho_id="reserva_objetivo#1",
            titulo="Reserva por objetivo",
            tema=TemaConhecimento.PRODUTO,
            texto="A reserva por objetivo separa o dinheiro de uma meta.",
            fonte=FonteTrecho(
                nome="Fonte sintética",
                referencia="Produto reserva_objetivo",
                url="https://exemplo.test/",
            ),
        ),
    ]


def _envelope(ferramenta: str, dados: BaseModel, corte: int) -> dict[str, Any]:
    resposta = Resposta[type(dados)](
        dados=dados,
        fonte=Fonte(
            ferramenta=ferramenta,
            tabelas=TABELAS_FERRAMENTA[ferramenta],
            periodo=Periodo(inicio=MESES[0], fim=corte),
        ),
        avisos=[],
    )
    return resposta.model_dump(mode="json")


def _golden(ferramenta: str, corte: int) -> BaseModel:
    meses = [m for m in MESES if m <= corte]
    n = len(meses)
    if ferramenta == "perfil_financeiro":
        return DadosPerfilFinanceiro(
            renda_media=5000.0 + n,
            gasto_medio=3000.0,
            sobra_media=2000.0 + n,
            sobra_mediana=2000.0,
            fontes_renda=[FonteRenda(macro="Renda", micro="Salario", media=5000.0)],
            saldo=Saldo(minimo=-50.0, maximo=1000.0 + n, atual=100.0 * n),
            serie_mensal=[
                PontoMensal(anomes=m, renda=5000.0, gasto=3000.0, sobra=2000.0) for m in meses
            ],
            meses_considerados=n,
        )
    if ferramenta == "capacidade_poupanca":
        return DadosCapacidadePoupanca(
            sobra_media=2000.0,
            sobra_mediana=2000.0,
            desvio_padrao=10.0,
            meses_negativos=0,
            meses_considerados=n,
        )
    if ferramenta == "oportunidades_corte":
        return DadosOportunidadesCorte(
            categorias=[
                Oportunidade(
                    macro="Lazer",
                    micro=f"Micro {i:02d}",
                    media_mensal=100.0 - i,
                    discricionaria=True,
                    economia_potencial_mensal=30.0 - i,
                    criterio="exemplo sintético",
                )
                for i in range(QTD_ITENS_GOLDEN)
            ]
        )
    if ferramenta == "dividas_e_parcelas":
        return DadosDividasParcelas(
            parcelas_ativas=[
                ParcelaAtiva(
                    descr="compra parcelada exemplo",
                    parcela_atual=n,
                    parcela_total=12,
                    valor=100.0,
                    meses_restantes=12 - n,
                )
            ],
            juros_pagos_media=5.0,
            comprometimento_renda_pct=2.0,
        )
    if ferramenta == "simular_objetivo":
        return DadosSimularObjetivo(
            modo="prazo",
            valor_alvo=ENTRADA_CANONICA_SIMULACAO["valor_alvo"],
            aporte_mensal=1250.0,
            prazo_meses=ENTRADA_CANONICA_SIMULACAO["prazo_meses"],
            viavel=True,
            folga_mensal=750.0,
            premissas={"rendimento_mensal": 0.0, "saldo_inicial": 0.0},
        )
    if ferramenta == "comparar_cenarios":
        regras = RegrasCenario()
        return DadosCompararCenarios(
            cenarios=[
                Cenario(
                    nome=nome,
                    pct_capacidade=pct,
                    aporte_mensal=round(2000.0 * pct, 2),
                    prazo_meses=24,
                    viavel=True,
                    cortes_sugeridos=(
                        [CorteSugerido(macro="Lazer", micro="Restaurantes", valor_mensal=50.0)]
                        if nome == "acelerado"
                        else []
                    ),
                    trade_offs=["exemplo sintético"],
                )
                for nome, pct in regras.pct_capacidade.items()
            ],
            regras=regras,
        )
    raise ValueError(ferramenta)


def gerar_fixtures_sinteticas(destino: Path) -> Path:
    """Grava em ``destino`` o layout de ``contracts/fixtures/`` com dados sintéticos."""
    _gravar(
        destino / "usuarios.json",
        _dump(
            [
                UsuarioFixture(id_usuario=ID_ANCORA, papel="ancora", faixa_renda=FAIXAS[ID_ANCORA]),
                UsuarioFixture(
                    id_usuario=ID_CONTROLE, papel="controle", faixa_renda=FAIXAS[ID_CONTROLE]
                ),
            ]
        ),
    )
    for nome, linhas in _tabelas().items():
        _gravar(destino / "bussola_dados" / f"{nome}.json", _dump(linhas))
    _gravar(destino / "rag" / "trechos_exemplo.json", _dump(trechos_sinteticos()))
    for ferramenta in FERRAMENTAS_GOLDEN:
        for corte in CORTES_GOLDEN:
            _gravar(
                destino / "ferramentas" / arquivo_golden(ferramenta, corte),
                _envelope(ferramenta, _golden(ferramenta, corte), corte),
            )
    for anomes in MESES_RESUMO_SINTETICO:
        dados = DadosResumoMes(
            anomes=anomes,
            renda=5000.0,
            gasto=3000.0,
            sobra=2000.0,
            gastos_macro=[
                GastoMacro(macro="Moradia", total=1500.0),
                GastoMacro(macro="Lazer", total=500.0),
            ],
        )
        envelope = _envelope("resumo_mes", dados, anomes)
        envelope["fonte"]["periodo"] = {"inicio": anomes, "fim": anomes}
        _gravar(destino / "ferramentas" / arquivo_resumo_mes(anomes), envelope)
    return destino


@pytest.fixture
def fixtures_sinteticas(tmp_path: Path) -> Path:
    """Diretório com o conjunto sintético de fixtures (layout de ``contracts/fixtures/``)."""
    return gerar_fixtures_sinteticas(tmp_path / "fixtures")
