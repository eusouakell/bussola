"""Fixtures dos testes do 006 (acompanhamento com replay temporal).

- Todo teste deste diretório recebe o marcador ``extensoes_reais``: o pacote
  ``bussola_agent.acompanhamento`` é importado na coleta e precisa manter a
  identidade do módulo (portas e registros) durante o teste.
- As portas do 006 e o registro do processo (``persistencia_bq``) voltam ao
  padrão antes e depois de cada teste.
- ``mcp``, ``gateway`` e ``registry`` ligam os fakes às portas.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from bussola_agent import persistencia_bq
from bussola_agent.acompanhamento import ports
from bussola_agent.acompanhamento.fakes import FixtureMcp, FixtureMcpGateway
from bussola_agent.persistencia import RegistroEmMemoria

_HERE = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if Path(str(item.path)).resolve().is_relative_to(_HERE):
            item.add_marker(pytest.mark.extensoes_reais)


@pytest.fixture(autouse=True)
def default_ports() -> Iterator[None]:
    ports.reset()
    persistencia_bq.set_default_registry(None)
    yield
    ports.reset()
    persistencia_bq.set_default_registry(None)


@pytest.fixture
def mcp() -> FixtureMcp:
    return FixtureMcp()


@pytest.fixture
def gateway(mcp: FixtureMcp) -> FixtureMcpGateway:
    adapter = FixtureMcpGateway(mcp)
    ports.configure_gateway(adapter)
    return adapter


@pytest.fixture
def registry() -> RegistroEmMemoria:
    fake = RegistroEmMemoria()
    ports.configure_registry(fake)
    return fake
