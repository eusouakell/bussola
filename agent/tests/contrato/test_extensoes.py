"""Pontos de extensão (contratos §6; AC-09, FR-014)."""

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from google.adk.tools import FunctionTool

from bussola_agent import callbacks, extensoes
from bussola_agent.extensoes import (
    PACOTES_EXTENSAO,
    carregar_extensoes,
    ferramentas,
    ferramentas_sensiveis,
    instrucoes,
    registrar_ferramenta,
    registrar_instrucao,
)


def registrar_objetivo(descricao: str) -> dict:
    """Ferramenta de exemplo."""
    return {"ok": descricao}


def criar_plano(cenario: str) -> dict:
    """Ferramenta sensível de exemplo."""
    return {"ok": cenario}


def test_pacotes_do_contrato() -> None:
    assert PACOTES_EXTENSAO == ("bussola_agent.governanca", "bussola_agent.acompanhamento")


@pytest.mark.usefixtures("sem_extensoes")
def test_carregar_sem_pacotes_nao_falha() -> None:
    """AC-09: governanca e acompanhamento ausentes (simulado com ``sem_extensoes``)."""
    for nome in PACOTES_EXTENSAO:
        assert importlib.util.find_spec(nome) is None
    carregar_extensoes()
    assert ferramentas() == []
    assert instrucoes() == ""
    assert ferramentas_sensiveis() == set()


def test_registro_de_ferramentas_e_sensiveis() -> None:
    registrar_ferramenta(registrar_objetivo)
    registrar_ferramenta(criar_plano, sensivel=True)
    assert ferramentas() == [registrar_objetivo, criar_plano]
    assert ferramentas_sensiveis() == {"criar_plano"}


def test_copias_defensivas() -> None:
    registrar_ferramenta(criar_plano, sensivel=True)
    ferramentas().clear()
    ferramentas_sensiveis().clear()
    assert ferramentas() == [criar_plano]
    assert ferramentas_sensiveis() == {"criar_plano"}


def test_nome_duplicado_gera_value_error() -> None:
    registrar_ferramenta(registrar_objetivo)

    def outra() -> dict:
        return {}

    outra.__name__ = "registrar_objetivo"
    with pytest.raises(ValueError):
        registrar_ferramenta(outra, sensivel=True)
    assert ferramentas() == [registrar_objetivo]
    assert ferramentas_sensiveis() == set()


def test_base_tool_usa_o_nome_do_adk() -> None:
    ferramenta = FunctionTool(criar_plano)
    registrar_ferramenta(ferramenta, sensivel=True)
    assert ferramentas() == [ferramenta]
    assert ferramentas_sensiveis() == {"criar_plano"}
    with pytest.raises(ValueError):
        registrar_ferramenta(criar_plano)


def test_ferramenta_sem_nome_ou_invalida() -> None:
    with pytest.raises(TypeError):
        registrar_ferramenta(lambda: None)
    with pytest.raises(TypeError):
        registrar_ferramenta("nao_e_ferramenta")  # type: ignore[arg-type]


def test_instrucoes_por_ordem_crescente() -> None:
    registrar_instrucao(70, "Trecho do 006.")
    registrar_instrucao(0, "  Trecho do 004.  ")
    registrar_instrucao(50, "Trecho do 005.")
    registrar_instrucao(50, "Segundo trecho do 005.")
    assert instrucoes() == (
        "Trecho do 004.\n\nTrecho do 005.\n\nSegundo trecho do 005.\n\nTrecho do 006."
    )


def test_instrucao_invalida() -> None:
    with pytest.raises(ValueError):
        registrar_instrucao(10, "   ")
    with pytest.raises(TypeError):
        registrar_instrucao("10", "texto")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        registrar_instrucao(10, None)  # type: ignore[arg-type]


def test_limpar() -> None:
    registrar_ferramenta(criar_plano, sensivel=True)
    registrar_instrucao(1, "x")
    extensoes.limpar()
    assert ferramentas() == [] and ferramentas_sensiveis() == set() and instrucoes() == ""


# ---------------------------------------------------------------------------
# Pacotes de extensão presentes (fixture ``criar_extensao`` do conftest)
# ---------------------------------------------------------------------------

CriarExtensao = Callable[[str, str], Path]


def test_pacote_presente_registra_ferramentas_instrucoes_e_callbacks(
    criar_extensao: CriarExtensao,
) -> None:
    criar_extensao(
        "governanca",
        "from bussola_agent import callbacks, extensoes\n"
        "def solicitar_consentimento(acao: str, resumo: str) -> dict:\n"
        "    return {}\n"
        "def criar_plano(cenario: str) -> dict:\n"
        "    return {}\n"
        "extensoes.registrar_ferramenta(solicitar_consentimento)\n"
        "extensoes.registrar_ferramenta(criar_plano, sensivel=True)\n"
        "extensoes.registrar_instrucao(50, 'Peça consentimento.')\n"
        "callbacks.registrar('before_tool', lambda **_: None, 20)\n",
    )
    carregar_extensoes()
    assert [f.__name__ for f in ferramentas()] == ["solicitar_consentimento", "criar_plano"]
    assert ferramentas_sensiveis() == {"criar_plano"}
    assert instrucoes() == "Peça consentimento."
    assert len(callbacks.registrados("before_tool")) == 1
    assert sys.modules.get("bussola_agent.acompanhamento") is None


def test_os_dois_pacotes_presentes(criar_extensao: CriarExtensao) -> None:
    criar_extensao(
        "governanca",
        "from bussola_agent import extensoes\nextensoes.registrar_instrucao(50, 'G')\n",
    )
    criar_extensao(
        "acompanhamento",
        "from bussola_agent import extensoes\nextensoes.registrar_instrucao(70, 'A')\n",
    )
    carregar_extensoes()
    assert instrucoes() == "G\n\nA"
    assert all(nome in sys.modules for nome in PACOTES_EXTENSAO)


def test_pacote_presente_com_erro_propaga(criar_extensao: CriarExtensao) -> None:
    """Q-04: um pacote presente com erro de import não é escondido."""
    criar_extensao("acompanhamento", "import modulo_que_nao_existe_xyz\n")
    with pytest.raises(ModuleNotFoundError):
        carregar_extensoes()


def test_pacote_presente_com_erro_de_registro_propaga(criar_extensao: CriarExtensao) -> None:
    criar_extensao(
        "governanca",
        "from bussola_agent import callbacks\ncallbacks.registrar('fase_errada', print, 1)\n",
    )
    with pytest.raises(ValueError):
        carregar_extensoes()
