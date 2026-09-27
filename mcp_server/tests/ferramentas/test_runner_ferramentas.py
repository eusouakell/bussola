"""Testes unitários do ``ToolRunner`` e do ``Computation`` (sem MCP e sem fixtures)."""

import pytest
from apoio_ferramentas import CalculosFixos, RepositorioSempreExiste, periodo
from pydantic import ValidationError

from bussola_mcp.contratos import (
    FERRAMENTAS,
    ID_ANCORA,
    MENSAGENS_ERRO,
    TABELAS_FERRAMENTA,
    CodigoErro,
    DadosCapacidadePoupanca,
    DadosResumoMes,
    EntradaSimularObjetivo,
)
from bussola_mcp.ferramentas import TOOL_MODULES
from bussola_mcp.ferramentas.base import ToolRunner, is_implausible_term
from bussola_mcp.ferramentas.ports import (
    BackendUnavailable,
    Computation,
    DomainError,
    FinancialComputations,
    ToolDependencies,
)

CAPACIDADE = DadosCapacidadePoupanca(
    sobra_media=1000.12,
    sobra_mediana=900.0,
    desvio_padrao=10.0,
    meses_negativos=0,
    meses_considerados=6,
)
ARGS = {"id_usuario": ID_ANCORA, "ate_anomes": 202512}


class RepositorioSemCliente:
    def usuario_existe(self, id_usuario: str) -> bool:
        return False


def _runner(computations=None, repository=None) -> ToolRunner:
    return ToolRunner(
        ToolDependencies(
            repository=repository or RepositorioSempreExiste(),
            searcher=None,  # type: ignore[arg-type]  # não usado nestes testes
            computations=computations or CalculosFixos(),
        )
    )


def _capacidade(deps, entrada):
    return deps.computations.capacidade_poupanca(entrada.id_usuario, entrada.ate_anomes)


def test_modulos_cobrem_as_9_ferramentas_na_ordem_do_contrato():
    assert [m.NAME for m in TOOL_MODULES] == list(FERRAMENTAS)
    for modulo in TOOL_MODULES:
        assert callable(modulo.compute) and callable(modulo.register)


def test_calculos_fixos_implementam_a_porta():
    assert isinstance(CalculosFixos(), FinancialComputations)


def test_sucesso_monta_envelope_com_fonte_e_avisos():
    calculos = CalculosFixos(
        resultado=Computation(dados=CAPACIDADE, periodo=periodo(202502, 202512), avisos=("a",))
    )
    envelope = _runner(calculos).run("capacidade_poupanca", dict(ARGS), _capacidade)
    assert envelope["fonte"] == {
        "ferramenta": "capacidade_poupanca",
        "tabelas": TABELAS_FERRAMENTA["capacidade_poupanca"],
        "periodo": {"inicio": 202502, "fim": 202512},
    }
    assert envelope["avisos"] == ["a"]
    assert envelope["dados"]["meses_considerados"] == 6
    assert calculos.chamadas == [("capacidade_poupanca", (ID_ANCORA, 202512))]


def test_id_normalizado_em_minusculas_antes_do_calculo():
    calculos = CalculosFixos(resultado=Computation(dados=CAPACIDADE, periodo=periodo()))
    _runner(calculos).run(
        "capacidade_poupanca", {**ARGS, "id_usuario": ID_ANCORA.upper()}, _capacidade
    )
    assert calculos.chamadas[0][1][0] == ID_ANCORA


def test_dados_de_outro_modelo_viram_indisponivel():
    """``dados`` que não batem com o modelo de §5 nunca saem (falha interna)."""
    errado = DadosResumoMes(anomes=202501, renda=1.0, gasto=1.0, sobra=0.0, gastos_macro=[])
    calculos = CalculosFixos(resultado=Computation(dados=errado, periodo=periodo()))
    envelope = _runner(calculos).run("capacidade_poupanca", dict(ARGS), _capacidade)
    assert envelope["erro"]["codigo"] == "INDISPONIVEL"


@pytest.mark.parametrize(
    "erro, esperado",
    [
        (
            DomainError(CodigoErro.DADOS_INSUFICIENTES),
            MENSAGENS_ERRO[CodigoErro.DADOS_INSUFICIENTES],
        ),
        (DomainError(CodigoErro.DADOS_INSUFICIENTES, "Sem meses."), "Sem meses."),
        (BackendUnavailable(), MENSAGENS_ERRO[CodigoErro.INDISPONIVEL]),
        (BackendUnavailable("Fora do ar."), "Fora do ar."),
        (KeyError("SELECT"), MENSAGENS_ERRO[CodigoErro.INDISPONIVEL]),
    ],
)
def test_excecoes_viram_envelope_de_erro(erro, esperado):
    envelope = _runner(CalculosFixos(erro=erro)).run("capacidade_poupanca", dict(ARGS), _capacidade)
    assert envelope["erro"]["mensagem"] == esperado


def test_usuario_inexistente_nao_chama_o_calculo():
    calculos = CalculosFixos()
    envelope = _runner(calculos, RepositorioSemCliente()).run(
        "capacidade_poupanca", dict(ARGS), _capacidade
    )
    assert envelope["erro"]["codigo"] == "USUARIO_INEXISTENTE"
    assert calculos.chamadas == []


def test_computation_with_avisos_sem_duplicar():
    base = Computation(dados=CAPACIDADE, periodo=periodo(), avisos=("a", "b"))
    assert base.with_avisos("b", "c", "c").avisos == ("a", "b", "c")
    assert base.avisos == ("a", "b")


def _erro_de(argumentos):
    with pytest.raises(ValidationError) as info:
        EntradaSimularObjetivo.model_validate(argumentos)
    return info.value


@pytest.mark.parametrize(
    "extra, esperado",
    [
        ({"valor_alvo": 10.0, "prazo_meses": 0}, True),
        ({"valor_alvo": 10.0, "prazo_meses": 361}, True),
        ({"valor_alvo": 10.0, "prazo_meses": 361, "aporte_mensal": 5.0}, False),
        ({"valor_alvo": -1.0, "prazo_meses": 361}, False),
        ({"valor_alvo": 10.0}, False),
        ({"valor_alvo": 10.0, "prazo_meses": "doze"}, False),
    ],
)
def test_is_implausible_term(extra, esperado):
    argumentos = {**ARGS, **extra}
    assert is_implausible_term(_erro_de(argumentos), argumentos) is esperado
