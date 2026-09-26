"""Testes offline de ``data/scripts/gerar_fixtures.py`` (T031, FR-015, FR-016).

Usam só linhas sintéticas montadas aqui (nada de BigQuery real nem rede). Os valores
esperados foram calculados à mão a partir das linhas.

Âncora sintético (12 meses, saldo inicial 500):

- dia 1: aluguel 1000 (saída; janeiro fica negativo);
- dia 5: salário 7000 (entrada);
- dia 10: streaming 100;
- dia 15: restaurante 300 + 10 × mês;
- dia 20: vestuário parcelado 200, parcela ``mês/12``;
- dia 25: juros do cheque especial 50, só de janeiro a março.

Controle sintético: salário 2000, supermercado 1500 e restaurante 100 por mês.
"""

import importlib.util
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from bussola_mcp.contratos import (
    CORTES_GOLDEN,
    FERRAMENTAS,
    FERRAMENTAS_P0,
    ID_ANCORA,
    ID_CONTROLE,
    MODELOS_TABELA,
    TABELAS_FERRAMENTA,
    Resposta,
    Trecho,
    UsuarioFixture,
    arquivo_golden,
    arquivo_resumo_mes,
)

RAIZ_REPO = Path(__file__).resolve().parents[3]


def _carregar_script(nome: str) -> ModuleType:
    caminho = RAIZ_REPO / "data" / "scripts" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"bussola_scripts_{nome}", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


gf = _carregar_script("gerar_fixtures")

ID_V1 = "a8098c1a-f86e-11da-bd1a-00112444be1e"  # UUID v1: formato válido, versão errada
ID_OUTRO_V4 = "0f8fad5b-d9cb-469f-a165-70867728950e"

# ---------------------------------------------------------------------------
# Dados sintéticos
# ---------------------------------------------------------------------------


def _linhas_usuario(
    id_usuario: str, saldo_inicial: float, itens_por_mes: Any
) -> list[dict[str, Any]]:
    """Linhas no formato de ``SQL_EXTRATO`` com a cadeia de ``saldo_apos`` coerente."""
    linhas: list[dict[str, Any]] = []
    saldo = saldo_inicial
    for mes in range(1, 13):
        for dia, tipo, descr, vlr, macro, micro, parcela in itens_por_mes(mes):
            saldo = round(saldo + (vlr if tipo == "E" else -vlr), 2)
            linhas.append(
                {
                    "id_usuario": id_usuario,
                    "anomesdia": datetime(2025, mes, dia),
                    "anomes": 202500 + mes,
                    "tipo": tipo,
                    "descr": descr,
                    "vlr": vlr,
                    "nom_cate_macro": macro,
                    "nom_cate_micro": micro,
                    "saldo_apos": saldo,
                    "parcela_atual": float(parcela[0]) if parcela else None,
                    "parcela_total": float(parcela[1]) if parcela else None,
                }
            )
    return linhas


def _itens_ancora(mes: int) -> list[tuple[Any, ...]]:
    itens = [
        (1, "S", "pix transf alug", 1000.0, "Moradia", "Aluguel", None),
        (5, "E", "pix recebido salario", 7000.0, "Renda", "Salário", None),
        (10, "S", "assin streaming video", 100.0, "Assinaturas", "Streaming", None),
        (15, "S", "restaurante centro", 300.0 + 10 * mes, "Alimentação", "Restaurantes", None),
        (
            20,
            "S",
            f"cart credito loja esport parc {mes}/12",
            200.0,
            "Compras",
            "Vestuário",
            (mes, 12),
        ),
    ]
    if mes <= 3:
        itens.append((25, "S", "juros cheque especial", 50.0, "Encargos", "Juros cheque", None))
    return itens


def _itens_controle(mes: int) -> list[tuple[Any, ...]]:
    return [
        (1, "E", "pix recebido salario", 2000.0, "Renda", "Salário", None),
        (3, "S", "compra mercado", 1500.0, "Alimentação", "Supermercado", None),
        (12, "S", "restaurante bairro", 100.0, "Alimentação", "Restaurantes", None),
    ]


def linhas_extrato() -> list[dict[str, Any]]:
    return _linhas_usuario(ID_ANCORA, 500.0, _itens_ancora) + _linhas_usuario(
        ID_CONTROLE, 100.0, _itens_controle
    )


PARES_CATEGORIAS = [
    ("Alimentação", "Restaurantes"),
    ("Alimentação", "Supermercado"),
    ("Saúde", "Farmácia"),
    ("Viagem", "Hotel"),
]


def linhas_coorte() -> list[dict[str, Any]]:
    linhas = [
        {"renda_media": 7000.0 + i, "macro": "Alimentação", "media_mensal": 100.0 * (i + 1)}
        for i in range(5)
    ]
    linhas += [{"renda_media": 8000.0, "macro": "Lazer", "media_mensal": 50.0} for _ in range(4)]
    linhas += [
        {"renda_media": 2000.0 + i, "macro": "Moradia", "media_mensal": 800.0 + 10 * i}
        for i in range(5)
    ]
    return linhas


def lancamentos() -> list[Any]:
    return [gf.lancamento_de_linha(linha) for linha in linhas_extrato()]


def coorte() -> list[Any]:
    return [gf.linha_coorte_de(linha) for linha in linhas_coorte()]


def gerar() -> dict[str, Any]:
    return gf.gerar_conjunto(lancamentos(), PARES_CATEGORIAS, coorte())


@pytest.fixture(scope="module")
def conjunto() -> dict[str, Any]:
    return gerar()


def _dados(conjunto: dict[str, Any], ferramenta: str, corte: int) -> dict[str, Any]:
    return conjunto[f"ferramentas/{arquivo_golden(ferramenta, corte)}"]["dados"]


def _linhas(conjunto: dict[str, Any], tabela: str, id_usuario: str = ID_ANCORA) -> list[dict]:
    return [
        linha
        for linha in conjunto[f"bussola_dados/{tabela}.json"]
        if linha.get("id_usuario") == id_usuario
    ]


# ---------------------------------------------------------------------------
# SQL parametrizado
# ---------------------------------------------------------------------------


def test_sql_de_referencia_e_parametrizado() -> None:
    for sql in (gf.SQL_EXTRATO, gf.SQL_CATEGORIAS, gf.SQL_COORTE):
        assert "@anomes_inicio" in sql and "@anomes_fim" in sql
        assert ID_ANCORA not in sql and ID_CONTROLE not in sql
        assert "202501" not in sql and "202512" not in sql
    assert "IN UNNEST(@ids_usuario)" in gf.SQL_EXTRATO
    colunas_coorte = gf.SQL_COORTE.split("SELECT u.renda_media")[1].split("FROM")[0]
    assert "id_usuario" not in colunas_coorte  # agregado anônimo

    parametros = {p.name: p for p in gf.parametros_extrato()}
    assert parametros["ids_usuario"].values == [ID_ANCORA, ID_CONTROLE]
    assert parametros["ids_usuario"].array_type == "STRING"
    assert (parametros["anomes_inicio"].value, parametros["anomes_fim"].value) == (202501, 202512)


# ---------------------------------------------------------------------------
# Regras das tabelas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("descr", "esperado"),
    [
        ("cart credito loja esport parc 1/12", "cart credito loja esport"),
        ("CART CREDITO  LOJA ESPORT PARC 12/12", "cart credito loja esport"),
        ("compra parcela 3 de 10 loja", "compra loja"),
        ("pix transf alug 05/03", "pix transf alug"),
        ("assin amazon prime 2025-01-10", "assin amazon prime"),
        ("assin amazon prime", "assin amazon prime"),
    ],
)
def test_normalizar_descr(descr: str, esperado: str) -> None:
    assert gf.normalizar_descr(descr) == esperado


def _lanc(dia: int, tipo: str, descr: str, vlr: float, saldo_apos: float) -> Any:
    return gf.Lancamento(
        id_usuario=ID_ANCORA,
        anomesdia=datetime(2025, 1, dia),
        anomes=202501,
        tipo=tipo,
        descr=descr,
        vlr=vlr,
        macro="M",
        micro="m",
        saldo_apos=saldo_apos,
    )


def test_empate_de_anomesdia_segue_cadeia_de_saldo() -> None:
    # Ordem real: E 1000 (0 → 1000), S b 100 (1000 → 900), E a 50 (900 → 950).
    # A ordem estável (tipo, descr) poria "E a" antes de "S b" e daria saldo final 900.
    linhas = [_lanc(1, "E", "z", 1000.0, 1000.0), _lanc(2, "E", "a", 50.0, 950.0)]
    linhas.append(_lanc(2, "S", "b", 100.0, 900.0))
    ordenados = gf.ordenar_lancamentos(reversed(linhas))
    assert [lanc.descr for lanc in ordenados] == ["z", "b", "a"]
    (perfil,) = gf.calcular_perfil_mensal(linhas)
    assert (perfil.saldo_inicial, perfil.saldo_final) == (0.0, 950.0)
    assert (perfil.saldo_minimo, perfil.saldo_maximo) == (900.0, 1000.0)


def test_empate_no_primeiro_lancamento_usa_saldo_que_ninguem_produz() -> None:
    # Ordem real: S x (500 → 400) e E y (400 → 600), no mesmo instante.
    linhas = [_lanc(1, "E", "y", 200.0, 600.0), _lanc(1, "S", "x", 100.0, 400.0)]
    (perfil,) = gf.calcular_perfil_mensal(linhas)
    assert (perfil.saldo_inicial, perfil.saldo_final, perfil.saldo_minimo) == (500.0, 600.0, 400.0)


def test_perfil_mensal_de_janeiro(conjunto: dict[str, Any]) -> None:
    janeiro = _linhas(conjunto, "perfil_mensal")[0]
    assert janeiro == {
        "id_usuario": ID_ANCORA,
        "anomes": 202501,
        "renda": 7000.0,
        "gasto": 1660.0,  # 1000 + 100 + 310 + 200 + 50
        "sobra": 5340.0,
        "saldo_inicial": 500.0,
        "saldo_final": 5840.0,
        "saldo_minimo": -500.0,
        "saldo_maximo": 6500.0,
        "juros": 50.0,
    }
    abril = _linhas(conjunto, "perfil_mensal")[3]
    assert (abril["gasto"], abril["juros"], abril["saldo_inicial"]) == (1640.0, 0.0, 16490.0)
    assert len(_linhas(conjunto, "perfil_mensal")) == 12
    assert len(_linhas(conjunto, "perfil_mensal", ID_CONTROLE)) == 12


def test_gastos_e_entradas_por_categoria(conjunto: dict[str, Any]) -> None:
    gastos = [g for g in _linhas(conjunto, "gastos_categoria") if g["anomes"] == 202502]
    assert {(g["micro"], g["total"], g["qtd"]) for g in gastos} == {
        ("Aluguel", 1000.0, 1),
        ("Streaming", 100.0, 1),
        ("Restaurantes", 320.0, 1),
        ("Vestuário", 200.0, 1),
        ("Juros cheque", 50.0, 1),
    }
    entradas = _linhas(conjunto, "entradas_categoria", ID_CONTROLE)
    assert len(entradas) == 12
    assert entradas[0] == {
        "id_usuario": ID_CONTROLE,
        "anomes": 202501,
        "macro": "Renda",
        "micro": "Salário",
        "total": 2000.0,
        "qtd": 1,
    }


def test_recorrentes_exige_tres_meses_e_so_saidas() -> None:
    def lanc(mes: int, tipo: str, descr: str) -> Any:
        return gf.Lancamento(
            ID_ANCORA, datetime(2025, mes, 1), 202500 + mes, tipo, descr, 10.0, "M", "m", 0.0
        )

    linhas = [lanc(m, "S", f"loja x parc {m}/3") for m in (1, 2, 3)]
    linhas += [lanc(m, "S", "cinema") for m in (1, 2)]
    linhas += [lanc(m, "E", "salario") for m in (1, 2, 3)]
    linhas.append(lanc(3, "S", "loja x parc 3/3"))  # mesmo mês: soma no valor
    recorrentes = gf.calcular_recorrentes(linhas)
    assert [(r.anomes, r.descr_norm, r.valor) for r in recorrentes] == [
        (202501, "loja x", 10.0),
        (202502, "loja x", 10.0),
        (202503, "loja x", 20.0),
    ]


def test_parcelas_so_com_parcela_total_maior_que_um(conjunto: dict[str, Any]) -> None:
    parcelas = _linhas(conjunto, "parcelas")
    assert len(parcelas) == 12
    assert parcelas[5] == {
        "id_usuario": ID_ANCORA,
        "anomes": 202506,
        "descr": "cart credito loja esport parc 6/12",
        "macro": "Compras",
        "parcela_atual": 6,
        "parcela_total": 12,
        "vlr": 200.0,
    }
    avulsa = gf.Lancamento(
        ID_ANCORA, datetime(2025, 1, 1), 202501, "S", "a vista", 5.0, "M", "m", 0.0, 1, 1
    )
    assert gf.calcular_parcelas([avulsa]) == []


@pytest.mark.parametrize(
    ("macro", "micro", "discricionaria", "pct"),
    [
        ("Assinaturas", "Streaming", True, 0.5),
        ("Alimentação", "Delivery", True, 0.5),
        ("Alimentação", "Restaurantes", True, 0.3),
        ("Compras", "Vestuário", True, 0.3),
        ("Lazer", "Outros", True, 0.3),
        ("Viagem", "Hotel", True, 0.2),
        ("Compras", "Supermercado", False, 0.0),
        ("Lazer", "Farmácia", False, 0.0),
        ("Moradia", "Aluguel", False, 0.0),
        ("Encargos", "Juros cheque", False, 0.0),
        ("Transporte", "Combustível", False, 0.0),
    ],
)
def test_classificar_categoria(macro: str, micro: str, discricionaria: bool, pct: float) -> None:
    categoria = gf.classificar_categoria(macro, micro)
    assert (categoria.discricionaria, categoria.corte_max_pct) == (discricionaria, pct)


def test_categorias_unem_catalogo_e_lancamentos(conjunto: dict[str, Any]) -> None:
    pares = [(c["macro"], c["micro"]) for c in conjunto["bussola_dados/categorias.json"]]
    assert pares == sorted(pares)
    assert ("Viagem", "Hotel") in pares  # só no catálogo
    assert ("Moradia", "Aluguel") in pares  # só nos lançamentos
    assert len(pares) == len(set(pares))


@pytest.mark.parametrize(
    ("renda", "faixa"),
    [
        (0.0, "ate_3k"),
        (2999.99, "ate_3k"),
        (3000.0, "3k_6k"),
        (6000.0, "6k_10k"),
        (9999.99, "6k_10k"),
        (10000.0, "10k_20k"),
        (20000.0, "acima_20k"),
    ],
)
def test_faixa_renda(renda: float, faixa: str) -> None:
    assert gf.faixa_renda(renda) == faixa


def test_referencia_coorte_exige_minimo_de_usuarios(conjunto: dict[str, Any]) -> None:
    assert conjunto["bussola_dados/referencia_coorte.json"] == [
        {
            "faixa_renda": "ate_3k",
            "macro": "Moradia",
            "media": 820.0,
            "mediana": 820.0,
            "qtd_usuarios": 5,
        },
        {
            "faixa_renda": "6k_10k",
            "macro": "Alimentação",
            "media": 300.0,
            "mediana": 300.0,
            "qtd_usuarios": 5,
        },
    ]  # "Lazer" (4 usuários) não é publicado


def test_usuarios(conjunto: dict[str, Any]) -> None:
    assert conjunto["usuarios.json"] == [
        {"id_usuario": ID_ANCORA, "papel": "ancora", "faixa_renda": "6k_10k"},
        {"id_usuario": ID_CONTROLE, "papel": "controle", "faixa_renda": "ate_3k"},
    ]


# ---------------------------------------------------------------------------
# Layout e validade
# ---------------------------------------------------------------------------


def _layout_esperado() -> set[str]:
    caminhos = {"usuarios.json", "rag/trechos_exemplo.json"}
    caminhos |= {
        f"bussola_dados/{t.split('.')[1]}.json"
        for t in MODELOS_TABELA
        if t.startswith("bussola_dados.")
    }
    caminhos |= {
        f"ferramentas/{arquivo_golden(f, c)}" for f in FERRAMENTAS_P0 for c in CORTES_GOLDEN
    }
    caminhos |= {f"ferramentas/{arquivo_resumo_mes(202500 + m)}" for m in range(1, 13)}
    return caminhos


def test_layout_do_conjunto(conjunto: dict[str, Any]) -> None:
    assert set(conjunto) == _layout_esperado()
    assert len(conjunto) == 35
    gf.validar_conjunto(conjunto)


def test_golden_validos_pelos_modelos(conjunto: dict[str, Any]) -> None:
    for caminho, obj in conjunto.items():
        if not caminho.startswith("ferramentas/"):
            continue
        ferramenta = Path(caminho).stem.split("__")[0]
        resposta = Resposta[FERRAMENTAS[ferramenta][1]].model_validate(obj)
        assert resposta.fonte.ferramenta == ferramenta
        assert resposta.fonte.tabelas == TABELAS_FERRAMENTA[ferramenta]
        if ferramenta == "resumo_mes":
            assert resposta.fonte.periodo.inicio == resposta.fonte.periodo.fim
        else:
            assert resposta.fonte.periodo.inicio == 202501
            assert resposta.fonte.periodo.fim == int(caminho[-11:-5])
    for linha in conjunto["usuarios.json"]:
        UsuarioFixture.model_validate(linha)
    for linha in conjunto["rag/trechos_exemplo.json"]:
        Trecho.model_validate(linha)


def test_validar_conjunto_rejeita_golden_invalido(conjunto: dict[str, Any]) -> None:
    quebrado = json.loads(json.dumps(conjunto))
    quebrado["ferramentas/perfil_financeiro__ate_202506.json"]["dados"]["extra"] = 1
    with pytest.raises(ValueError):
        gf.validar_conjunto(quebrado)
    fora = {"outros/x.json": []}
    with pytest.raises(gf.ErroDados):
        gf.validar_conjunto(fora)


def test_gravar_em_tmp_path(conjunto: dict[str, Any], tmp_path: Path) -> None:
    caminhos = gf.gravar(tmp_path / "fixtures", conjunto)
    relativos = {p.relative_to(tmp_path / "fixtures").as_posix() for p in caminhos}
    assert relativos == _layout_esperado()
    arquivo = tmp_path / "fixtures" / "bussola_dados" / "categorias.json"
    texto = arquivo.read_text(encoding="utf-8")
    assert "Alimentação" in texto  # ensure_ascii=False
    assert texto.endswith("\n") and texto.startswith("[\n  {")
    assert json.loads(texto) == conjunto["bussola_dados/categorias.json"]
    golden = (tmp_path / "fixtures" / "ferramentas" / "resumo_mes__202501.json").read_text("utf-8")
    assert (
        golden
        == json.dumps(
            conjunto["ferramentas/resumo_mes__202501.json"],
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def test_determinismo_independe_da_ordem_de_entrada() -> None:
    base = {caminho: gf.serializar(obj) for caminho, obj in gerar().items()}
    linhas = lancamentos()
    random.Random(7).shuffle(linhas)
    pares = list(reversed(PARES_CATEGORIAS))
    linhas_c = list(reversed(coorte()))
    embaralhado = gf.gerar_conjunto(linhas, pares, linhas_c)
    assert {caminho: gf.serializar(obj) for caminho, obj in embaralhado.items()} == base


# ---------------------------------------------------------------------------
# Golden P0 (valores à mão)
# ---------------------------------------------------------------------------


def test_golden_perfil_financeiro(conjunto: dict[str, Any]) -> None:
    dados = _dados(conjunto, "perfil_financeiro", 202506)
    assert dados["renda_media"] == 7000.0
    assert dados["gasto_medio"] == 1660.0  # (1660+1670+1680+1640+1650+1660) / 6
    assert (dados["sobra_media"], dados["sobra_mediana"]) == (5340.0, 5340.0)
    assert dados["fontes_renda"] == [{"macro": "Renda", "micro": "Salário", "media": 7000.0}]
    assert dados["saldo"] == {"minimo": -500.0, "maximo": 33200.0, "atual": 32540.0}
    assert [p["anomes"] for p in dados["serie_mensal"]] == list(range(202501, 202507))
    assert dados["meses_considerados"] == 6
    resposta = conjunto["ferramentas/perfil_financeiro__ate_202506.json"]
    assert resposta["avisos"] == ["Saldo ficou negativo em 1 mês do período."]
    assert _dados(conjunto, "perfil_financeiro", 202512)["meses_considerados"] == 12


def test_golden_capacidade_poupanca(conjunto: dict[str, Any]) -> None:
    dados = _dados(conjunto, "capacidade_poupanca", 202506)
    # sobras 5340, 5330, 5320, 5360, 5350, 5340: desvios 0, -10, -20, 20, 10, 0
    assert dados == {
        "sobra_media": 5340.0,
        "sobra_mediana": 5340.0,
        "desvio_padrao": 12.91,  # sqrt(1000 / 6), populacional
        "meses_negativos": 0,
        "meses_considerados": 6,
    }


def test_golden_oportunidades_corte(conjunto: dict[str, Any]) -> None:
    categorias = _dados(conjunto, "oportunidades_corte", 202506)["categorias"]
    assert [
        (c["micro"], c["media_mensal"], c["economia_potencial_mensal"]) for c in categorias
    ] == [
        ("Restaurantes", 335.0, 100.5),  # (310+320+330+340+350+360) / 6 × 0,3
        ("Vestuário", 200.0, 60.0),
        ("Streaming", 100.0, 50.0),
    ]
    assert all(c["discricionaria"] for c in categorias)
    assert categorias[0]["criterio"].startswith("Categoria discricionária: corte de até 30%")


def test_golden_dividas_e_parcelas(conjunto: dict[str, Any]) -> None:
    dados = _dados(conjunto, "dividas_e_parcelas", 202506)
    assert dados["parcelas_ativas"] == [
        {
            "descr": "cart credito loja esport parc 6/12",
            "parcela_atual": 6,
            "parcela_total": 12,
            "valor": 200.0,
            "meses_restantes": 6,
        }
    ]
    assert dados["juros_pagos_media"] == 25.0  # 150 / 6
    assert dados["comprometimento_renda_pct"] == 2.86  # 200 / 7000 × 100
    final = _dados(conjunto, "dividas_e_parcelas", 202512)
    assert final["parcelas_ativas"][0]["meses_restantes"] == 0
    assert final["juros_pagos_media"] == 12.5


def test_golden_simular_objetivo(conjunto: dict[str, Any]) -> None:
    dados = _dados(conjunto, "simular_objetivo", 202506)
    assert dados["modo"] == "prazo"
    assert (dados["valor_alvo"], dados["prazo_meses"], dados["aporte_mensal"]) == (
        30000.0,
        24,
        1250.0,
    )
    assert (dados["viavel"], dados["folga_mensal"]) == (True, 4090.0)
    assert dados["premissas"]["capacidade_mensal"] == 5340.0
    assert dados["premissas"]["rendimento_mensal"] == 0.0


def test_simulacao_modo_aporte_e_saldo_atual() -> None:
    perfil = gf.calcular_perfil_mensal(lancamentos())
    meses = [p for p in perfil if p.id_usuario == ID_ANCORA and p.anomes <= 202506]
    resultado, avisos = gf.calcular_simulacao(meses, 30000.0, aporte_mensal=1000.0)
    assert (resultado.modo, resultado.prazo_meses, resultado.aporte_mensal) == (
        "aporte",
        30,
        1000.0,
    )
    assert avisos == []
    resultado, _ = gf.calcular_simulacao(meses, 30000.0, prazo_meses=10, usar_saldo_atual=True)
    assert resultado.premissas["saldo_inicial"] == 32540.0
    assert (resultado.aporte_mensal, resultado.viavel) == (0.0, True)
    resultado, avisos = gf.calcular_simulacao(meses, 300000.0, prazo_meses=12)
    assert (resultado.aporte_mensal, resultado.viavel) == (25000.0, False)
    assert avisos == ["O aporte necessário supera a sobra mensal mediana."]
    with pytest.raises(ValueError):
        gf.calcular_simulacao(meses, 1.0, prazo_meses=1, aporte_mensal=1.0)


def test_golden_comparar_cenarios(conjunto: dict[str, Any]) -> None:
    dados = _dados(conjunto, "comparar_cenarios", 202506)
    resumo = [
        (c["nome"], c["aporte_mensal"], c["prazo_meses"], c["viavel"], len(c["cortes_sugeridos"]))
        for c in dados["cenarios"]
    ]
    assert resumo == [
        ("conservador", 2136.0, 15, True, 0),  # 0,4 × 5340; ⌈30000 / 2136⌉
        ("equilibrado", 3204.0, 10, True, 0),
        ("acelerado", 4482.5, 7, True, 3),  # 0,8 × 5340 + 100,5 + 60 + 50
    ]
    acelerado = dados["cenarios"][2]
    assert acelerado["trade_offs"] == [
        "Atinge a meta em 7 meses, dentro do prazo de 24 meses.",
        "Compromete 80% da sobra mensal mediana (R$ 4.272/mês).",
        "Exige reduzir R$ 100/mês em Restaurantes.",
        "Exige reduzir R$ 60/mês em Vestuário.",
        "Exige reduzir R$ 50/mês em Streaming.",
    ]
    assert dados["regras"]["pct_capacidade"] == {
        "conservador": 0.4,
        "equilibrado": 0.6,
        "acelerado": 0.8,
    }


def test_golden_buscar_contexto(conjunto: dict[str, Any]) -> None:
    ate_junho = _dados(conjunto, "buscar_contexto_financeiro", 202506)["trechos"]
    assert [t["doc_id"] for t in ate_junho] == [
        "coorte:6k_10k:alimentacao",
        *[f"ficha_mensal:{ID_ANCORA}:{m}" for m in range(202506, 202500, -1)],
    ]
    ate_dezembro = _dados(conjunto, "buscar_contexto_financeiro", 202512)["trechos"]
    assert len(ate_dezembro) == 10
    assert ate_dezembro[0]["doc_id"] == f"perfil_anual:{ID_ANCORA}:2025"
    scores = [t["score"] for t in ate_dezembro]
    assert scores == sorted(scores, reverse=True)
    assert all(t["origem"]["id_usuario"] in (ID_ANCORA, None) for t in ate_dezembro)


def test_trechos_rag(conjunto: dict[str, Any]) -> None:
    trechos = conjunto["rag/trechos_exemplo.json"]
    tipos = {t["tipo"] for t in trechos}
    assert tipos == {"ficha_mensal", "perfil_anual", "coorte"}
    assert len(trechos) == 12 + 12 + 1 + 1
    assert any(t["origem"]["id_usuario"] == ID_CONTROLE for t in trechos)
    (coorte_,) = [t for t in trechos if t["tipo"] == "coorte"]
    assert (coorte_["anomes"], coorte_["origem"]) == (
        None,
        {"id_usuario": None, "anomes": None, "categoria": "Alimentação"},
    )
    assert coorte_["texto"] == (
        "Clientes com renda entre R$ 6 mil e R$ 10 mil gastam em média R$ 300/mês com "
        "Alimentação (mediana R$ 300, 5 clientes)."
    )
    descrs = {linha["descr"] for linha in linhas_extrato()}
    for trecho in trechos:
        assert not any(descr in trecho["texto"] for descr in descrs)


def test_resumo_mes(conjunto: dict[str, Any]) -> None:
    resposta = conjunto["ferramentas/resumo_mes__202501.json"]
    assert resposta["dados"] == {
        "anomes": 202501,
        "renda": 7000.0,
        "gasto": 1660.0,
        "sobra": 5340.0,
        "gastos_macro": [
            {"macro": "Moradia", "total": 1000.0},
            {"macro": "Alimentação", "total": 310.0},
            {"macro": "Compras", "total": 200.0},
            {"macro": "Assinaturas", "total": 100.0},
            {"macro": "Encargos", "total": 50.0},
        ],
    }
    assert resposta["fonte"]["periodo"] == {"inicio": 202501, "fim": 202501}
    assert resposta["avisos"] == ["Saldo ficou negativo neste mês."]
    assert conjunto["ferramentas/resumo_mes__202512.json"]["avisos"] == []


# ---------------------------------------------------------------------------
# Validação da origem
# ---------------------------------------------------------------------------


def test_uuid_nao_v4_aborta_sem_ecoar_o_valor() -> None:
    linhas = linhas_extrato()
    for linha in linhas[:3]:
        linha["id_usuario"] = ID_V1
    with pytest.raises(gf.ErroDados) as erro:
        gf.gerar_conjunto([gf.lancamento_de_linha(li) for li in linhas], [], coorte())
    assert "UUID v4" in str(erro.value)
    assert ID_V1 not in str(erro.value)


def test_usuario_inesperado_ou_ausente_aborta() -> None:
    linhas = linhas_extrato()
    linhas[0]["id_usuario"] = ID_OUTRO_V4
    with pytest.raises(gf.ErroDados, match="fora dos usuários de fixture"):
        gf.gerar_conjunto([gf.lancamento_de_linha(li) for li in linhas], [], coorte())
    so_controle = [li for li in linhas_extrato() if li["id_usuario"] == ID_CONTROLE]
    with pytest.raises(gf.ErroDados, match="âncora"):
        gf.gerar_conjunto([gf.lancamento_de_linha(li) for li in so_controle], [], coorte())


def test_id_em_maiusculas_e_normalizado() -> None:
    linhas = linhas_extrato()
    for linha in linhas:
        linha["id_usuario"] = linha["id_usuario"].upper()
    conjunto = gf.gerar_conjunto([gf.lancamento_de_linha(li) for li in linhas], [], coorte())
    assert conjunto["usuarios.json"][0]["id_usuario"] == ID_ANCORA


def test_sem_coorte_da_faixa_do_ancora_aborta() -> None:
    with pytest.raises(gf.ErroDados, match="coorte"):
        gf.gerar_conjunto(lancamentos(), [], [])


# ---------------------------------------------------------------------------
# CLI com cliente BigQuery falso
# ---------------------------------------------------------------------------


class _Job:
    def __init__(self, linhas: list[dict[str, Any]]) -> None:
        self._linhas = linhas

    def result(self) -> list[dict[str, Any]]:
        return self._linhas


class ClienteFalso:
    def __init__(self, extrato: list[dict[str, Any]]) -> None:
        self.respostas = {
            gf.SQL_EXTRATO: extrato,
            gf.SQL_CATEGORIAS: [{"macro": m, "micro": n} for m, n in PARES_CATEGORIAS],
            gf.SQL_COORTE: linhas_coorte(),
        }
        self.chamadas: list[tuple[str, Any]] = []

    def query(self, sql: str, job_config: Any = None) -> _Job:
        self.chamadas.append((sql, job_config))
        return _Job(self.respostas[sql])


def test_main_grava_fixtures_com_cliente_falso(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clientes: list[tuple[str, ClienteFalso]] = []

    def fabrica(projeto: str) -> ClienteFalso:
        cliente = ClienteFalso(linhas_extrato())
        clientes.append((projeto, cliente))
        return cliente

    saida = tmp_path / "fixtures"
    codigo = gf.main(["--saida", str(saida), "--projeto", "projeto-teste"], criar_cliente=fabrica)
    assert codigo == 0
    ((projeto, cliente),) = clientes
    assert projeto == "projeto-teste"
    assert [sql for sql, _ in cliente.chamadas] == [
        gf.SQL_EXTRATO,
        gf.SQL_CATEGORIAS,
        gf.SQL_COORTE,
    ]
    parametros = {p.name: p for p in cliente.chamadas[0][1].query_parameters}
    assert parametros["ids_usuario"].values == [ID_ANCORA, ID_CONTROLE]
    gravados = {p.relative_to(saida).as_posix() for p in saida.rglob("*.json")}
    assert gravados == _layout_esperado()
    assert (saida / "usuarios.json").read_text(encoding="utf-8") == gf.serializar(
        gerar()["usuarios.json"]
    )
    assert "35 arquivos gravados" in capsys.readouterr().out


def test_main_usa_google_cloud_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "projeto-env")
    projetos: list[str] = []

    def fabrica(projeto: str) -> ClienteFalso:
        projetos.append(projeto)
        return ClienteFalso(linhas_extrato())

    assert gf.main(["--saida", str(tmp_path)], criar_cliente=fabrica) == 0
    assert projetos == ["projeto-env"]


def test_main_sem_projeto_nao_cria_cliente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    def fabrica(projeto: str) -> None:
        raise AssertionError("não deveria criar cliente")

    assert gf.main(["--saida", str(tmp_path / "x")], criar_cliente=fabrica) == 2
    assert "GOOGLE_CLOUD_PROJECT" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


def test_main_com_uuid_invalido_nao_grava_nada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    linhas = linhas_extrato()
    linhas[0]["id_usuario"] = ID_V1
    saida = tmp_path / "fixtures"
    codigo = gf.main(
        ["--saida", str(saida), "--projeto", "p"], criar_cliente=lambda _: ClienteFalso(linhas)
    )
    assert codigo == 1
    assert not saida.exists()
    erro = capsys.readouterr().err
    assert "UUID v4" in erro and ID_V1 not in erro


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as saida:
        gf.main(["--help"])
    assert saida.value.code == 0
    texto = capsys.readouterr().out
    assert "--saida" in texto and "--projeto" in texto
