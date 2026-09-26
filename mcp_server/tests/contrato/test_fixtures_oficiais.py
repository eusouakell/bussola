"""Fixtures oficiais em ``contracts/fixtures/`` (AC-04, T023).

Os testes das fixtures oficiais são pulados, com motivo, enquanto ``make fixtures`` não
tiver gerado ``usuarios.json`` (precisa de credenciais GCP). O cálculo dos valores de
referência também roda sobre as fixtures sintéticas, para não ficar sem teste.
"""

import json
import math
import unicodedata
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from bussola_mcp.contratos import (
    CORTES_GOLDEN,
    FERRAMENTAS,
    FERRAMENTAS_P0,
    ID_ANCORA,
    ID_CONTROLE,
    MODELOS_TABELA,
    GastoCategoria,
    PerfilMes,
    Resposta,
    Trecho,
    UsuarioFixture,
    arquivo_golden,
    arquivo_resumo_mes,
)

DIR_OFICIAL = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
MESES_2025 = tuple(range(202501, 202513))
TOLERANCIA = 0.01
MAX_ITENS_GOLDEN = 10

# Contratos §8: médias mensais do âncora em 2025 (ate_anomes = 202512).
VALORES_REFERENCIA: dict[str, float] = {
    "renda": 7451.0,
    "gasto": 4615.0,
    "sobra": 2836.0,
    "aluguel": 1077.0,
    "comer_fora": 364.0,
    "assinaturas": 101.0,
    "juros": 61.0,
    "saldo_minimo": -2072.0,
    "saldo_maximo": 49321.0,
}

# Os documentos não fixam os nomes das categorias: casamento por palavra-chave no texto
# normalizado de "macro micro" (mesma ideia das regras provisórias de data/scripts).
PALAVRAS_CATEGORIA: dict[str, tuple[str, ...]] = {
    "aluguel": ("aluguel",),
    "comer_fora": ("restaurante", "comer fora"),
    "assinaturas": ("assinatura", "streaming"),
}

sem_fixtures_oficiais = pytest.mark.skipif(
    not (DIR_OFICIAL / "usuarios.json").is_file(),
    reason=(
        "contracts/fixtures/usuarios.json ausente: rode `make fixtures` com credenciais GCP "
        "(AC-04, T032)"
    ),
)


# -- leitura e cálculo ----------------------------------------------------------------


def ler(dir_fixtures: Path, relativo: str) -> Any:
    caminho = dir_fixtures / relativo
    assert caminho.is_file(), f"fixture ausente: {relativo}"
    return json.loads(caminho.read_text(encoding="utf-8"))


def linhas[M: BaseModel](dir_fixtures: Path, tabela: str, modelo: type[M]) -> list[M]:
    conteudo = ler(dir_fixtures, f"bussola_dados/{tabela}.json")
    assert isinstance(conteudo, list), f"{tabela}: esperado uma lista de linhas"
    return [modelo.model_validate(linha) for linha in conteudo]


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.casefold().split())


def _da_categoria(gasto: GastoCategoria, palavras: tuple[str, ...]) -> bool:
    texto = _normalizar(f"{gasto.macro} {gasto.micro}")
    return any(palavra in texto for palavra in palavras)


def valores_do_cliente(dir_fixtures: Path, id_usuario: str) -> dict[str, float]:
    """Médias mensais de 2025 do cliente, calculadas a partir das tabelas das fixtures."""
    meses = [
        p
        for p in linhas(dir_fixtures, "perfil_mensal", PerfilMes)
        if p.id_usuario == id_usuario and p.anomes in MESES_2025
    ]
    assert meses, "cliente sem perfil_mensal em 2025"
    qtd = len(meses)
    gastos = [
        g
        for g in linhas(dir_fixtures, "gastos_categoria", GastoCategoria)
        if g.id_usuario == id_usuario and g.anomes in MESES_2025
    ]
    valores = {
        "renda": math.fsum(p.renda for p in meses) / qtd,
        "gasto": math.fsum(p.gasto for p in meses) / qtd,
        "sobra": math.fsum(p.sobra for p in meses) / qtd,
        "juros": math.fsum(p.juros for p in meses) / qtd,
        "saldo_minimo": min(p.saldo_minimo for p in meses),
        "saldo_maximo": max(p.saldo_maximo for p in meses),
    }
    for nome, palavras in PALAVRAS_CATEGORIA.items():
        total = math.fsum(g.total for g in gastos if _da_categoria(g, palavras))
        valores[nome] = total / qtd
    return valores


def test_calculo_dos_valores_sobre_fixtures_sinteticas(fixtures_sinteticas):
    """A conta de AC-04 usa só o cliente pedido e divide pelos meses de 2025."""
    valores = valores_do_cliente(fixtures_sinteticas, ID_ANCORA)
    assert set(valores) == set(VALORES_REFERENCIA)
    assert valores["renda"] == pytest.approx(5055.0)
    assert valores["gasto"] == pytest.approx(3000.0)
    assert valores["sobra"] == pytest.approx(2055.0)
    assert valores["aluguel"] == pytest.approx(1500.0)
    assert valores["comer_fora"] == pytest.approx(500.0)
    assert valores["assinaturas"] == 0.0
    assert valores["juros"] == pytest.approx(5.0)
    assert valores["saldo_minimo"] == -50.0
    assert valores["saldo_maximo"] == 1011.0
    assert valores_do_cliente(fixtures_sinteticas, ID_CONTROLE)["aluguel"] == pytest.approx(900.0)


# -- fixtures oficiais (AC-04) ------------------------------------------------------------


@sem_fixtures_oficiais
def test_usuarios_oficiais():
    usuarios = [UsuarioFixture.model_validate(u) for u in ler(DIR_OFICIAL, "usuarios.json")]
    assert {(u.id_usuario, u.papel) for u in usuarios} == {
        (ID_ANCORA, "ancora"),
        (ID_CONTROLE, "controle"),
    }


@sem_fixtures_oficiais
@pytest.mark.parametrize(
    "tabela", sorted(t for t in MODELOS_TABELA if t.startswith("bussola_dados."))
)
def test_tabelas_oficiais_validam_nos_modelos(tabela):
    nome = tabela.removeprefix("bussola_dados.")
    modelo = MODELOS_TABELA[tabela]
    validadas = linhas(DIR_OFICIAL, nome, modelo)
    if "id_usuario" in modelo.model_fields:
        assert validadas, f"{nome} sem linhas"
        assert {linha.id_usuario for linha in validadas} <= {ID_ANCORA, ID_CONTROLE}
    if "anomes" in modelo.model_fields:
        assert all(linha.anomes in MESES_2025 for linha in validadas)


@sem_fixtures_oficiais
@pytest.mark.parametrize("corte", CORTES_GOLDEN)
@pytest.mark.parametrize("ferramenta", FERRAMENTAS_P0)
def test_golden_p0_valida_no_modelo(ferramenta, corte):
    _, dados = FERRAMENTAS[ferramenta]
    envelope = Resposta[dados].model_validate(
        ler(DIR_OFICIAL, f"ferramentas/{arquivo_golden(ferramenta, corte)}")
    )
    assert envelope.fonte.ferramenta == ferramenta
    assert envelope.fonte.periodo.fim <= corte
    if ferramenta == "oportunidades_corte":
        assert len(envelope.dados.categorias) <= MAX_ITENS_GOLDEN
    if ferramenta == "buscar_contexto_financeiro":
        trechos = envelope.dados.trechos
        assert len(trechos) <= MAX_ITENS_GOLDEN
        assert all(t.origem.id_usuario in (ID_ANCORA, None) for t in trechos)
        assert all(t.anomes is None or t.anomes <= corte for t in trechos)


@sem_fixtures_oficiais
@pytest.mark.parametrize("anomes", MESES_2025)
def test_resumo_mes_valida_no_modelo(anomes):
    _, dados = FERRAMENTAS["resumo_mes"]
    envelope = Resposta[dados].model_validate(
        ler(DIR_OFICIAL, f"ferramentas/{arquivo_resumo_mes(anomes)}")
    )
    assert envelope.dados.anomes == anomes


@sem_fixtures_oficiais
def test_trechos_oficiais_validam_no_modelo():
    trechos = [Trecho.model_validate(t) for t in ler(DIR_OFICIAL, "rag/trechos_exemplo.json")]
    assert trechos
    assert {t.origem.id_usuario for t in trechos} <= {ID_ANCORA, ID_CONTROLE, None}


@sem_fixtures_oficiais
@pytest.mark.parametrize("metrica", sorted(VALORES_REFERENCIA))
def test_valores_de_referencia_do_ancora(metrica):
    calculado = valores_do_cliente(DIR_OFICIAL, ID_ANCORA)[metrica]
    assert calculado == pytest.approx(VALORES_REFERENCIA[metrica], rel=TOLERANCIA), metrica


@sem_fixtures_oficiais
def test_golden_perfil_bate_com_as_tabelas():
    _, dados = FERRAMENTAS["perfil_financeiro"]
    golden = (
        Resposta[dados]
        .model_validate(
            ler(DIR_OFICIAL, f"ferramentas/{arquivo_golden('perfil_financeiro', 202512)}")
        )
        .dados
    )
    valores = valores_do_cliente(DIR_OFICIAL, ID_ANCORA)
    assert golden.renda_media == pytest.approx(valores["renda"], abs=0.01)
    assert golden.gasto_medio == pytest.approx(valores["gasto"], abs=0.01)
    assert golden.sobra_media == pytest.approx(valores["sobra"], abs=0.01)
    assert golden.saldo.minimo == pytest.approx(valores["saldo_minimo"], abs=0.01)
    assert golden.saldo.maximo == pytest.approx(valores["saldo_maximo"], abs=0.01)
