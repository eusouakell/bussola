"""Fixtures comuns dos testes do agente.

- Guarda de rede (autouse): só conexões locais (loopback ou socket Unix) são
  permitidas. Uma tentativa de acesso externo levanta
  :class:`RedeBloqueadaError` e faz o teste falhar, mesmo que o código
  capture a exceção. Testes marcados com ``bq`` ficam de fora.
- Registros de callbacks e extensões esvaziados antes e depois de cada teste.
- ``BUSSOLA_FAKES=TRUE``, ``MCP_USE_OIDC`` removido (nenhum ID token real) e
  ``GOOGLE_API_USE_CLIENT_CERTIFICATE=false``: sem isso o ``McpToolset`` do ADK
  chama ``google.auth.default()`` na primeira conexão para tentar mTLS, o que lê
  credenciais locais e pode consultar o metadata server do GCE.
- ``criar_extensao``: cria pacotes de extensão (``governanca``,
  ``acompanhamento``) num diretório temporário visível como
  ``bussola_agent.<nome>`` e os descarrega no fim do teste. O diretório
  temporário tem prioridade sobre os pacotes reais (acréscimo do 005).
- ``sem_extensoes``: simula a ausência dos pacotes de extensão, mesmo quando o
  pacote real existe (acréscimo do 005).
"""

import importlib
import ipaddress
import socket
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

import bussola_agent
from bussola_agent import callbacks, extensoes
from bussola_agent.extensoes import PACOTES_EXTENSAO

_HOSTS_LOCAIS = {"localhost", "localhost.", "ip6-localhost"}


class RedeBloqueadaError(RuntimeError):
    """Tentativa de acesso à rede fora de loopback durante os testes."""


def _host_local(host: Any) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    if not isinstance(host, str):
        return False
    host = host.strip("[]").split("%", 1)[0]
    if host == "" or host.lower() in _HOSTS_LOCAIS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _endereco_local(sock: socket.socket, endereco: Any) -> bool:
    if getattr(socket, "AF_UNIX", None) is not None and sock.family == socket.AF_UNIX:
        return True
    if isinstance(endereco, tuple) and endereco:
        return _host_local(endereco[0])
    return False


@pytest.fixture(autouse=True)
def guarda_de_rede(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    if request.node.get_closest_marker("bq") is not None:
        yield
        return

    tentativas: list[str] = []
    connect_original = socket.socket.connect
    connect_ex_original = socket.socket.connect_ex
    getaddrinfo_original = socket.getaddrinfo

    def _bloquear(descricao: str) -> None:
        tentativas.append(descricao)
        raise RedeBloqueadaError("Acesso à rede fora de loopback bloqueado nos testes.")

    def connect(self: socket.socket, endereco: Any) -> Any:
        if not _endereco_local(self, endereco):
            _bloquear("connect")
        return connect_original(self, endereco)

    def connect_ex(self: socket.socket, endereco: Any) -> Any:
        if not _endereco_local(self, endereco):
            _bloquear("connect_ex")
        return connect_ex_original(self, endereco)

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if not _host_local(host):
            _bloquear("getaddrinfo")
        return getaddrinfo_original(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield
    if tentativas:
        chamadas = ", ".join(sorted(set(tentativas)))
        pytest.fail(f"O teste tentou acessar a rede fora de loopback ({chamadas}).")


@pytest.fixture(autouse=True)
def registros_limpos() -> Iterator[None]:
    callbacks.limpar()
    extensoes.limpar()
    yield
    callbacks.limpar()
    extensoes.limpar()


@pytest.fixture(autouse=True)
def ambiente_de_teste(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUSSOLA_FAKES", "TRUE")
    monkeypatch.delenv("MCP_USE_OIDC", raising=False)
    monkeypatch.setenv("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")


def _descarregar_extensoes() -> None:
    for nome in PACOTES_EXTENSAO:
        sys.modules.pop(nome, None)
        curto = nome.rsplit(".", 1)[1]
        if hasattr(bussola_agent, curto):
            delattr(bussola_agent, curto)
    importlib.invalidate_caches()


@pytest.fixture
def criar_extensao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[[str, str], Path]]:
    """Fábrica ``criar_extensao(nome, codigo)`` de pacotes ``bussola_agent.<nome>``.

    O diretório temporário entra **na frente** do ``__path__`` de
    ``bussola_agent``, para o pacote falso ter prioridade sobre o real; o
    ``__init__.py`` do pacote recebe ``codigo``.
    """
    raiz = tmp_path / "extensoes"
    raiz.mkdir()
    monkeypatch.setattr(bussola_agent, "__path__", [str(raiz), *bussola_agent.__path__])
    _descarregar_extensoes()

    def criar(nome: str, codigo: str) -> Path:
        pacote = raiz / nome
        pacote.mkdir()
        (pacote / "__init__.py").write_text(codigo, encoding="utf-8")
        importlib.invalidate_caches()
        return pacote

    yield criar
    _descarregar_extensoes()


@pytest.fixture
def sem_extensoes() -> Iterator[None]:
    """Simula a ausência de ``governanca`` e ``acompanhamento`` (acréscimo do 005).

    ``sys.modules[nome] = None`` faz ``importlib.util.find_spec`` devolver
    ``None`` e o ``import`` falhar, como se o pacote não existisse. Os pacotes
    são descarregados antes e depois do teste.
    """
    _descarregar_extensoes()
    for nome in PACOTES_EXTENSAO:
        sys.modules[nome] = None  # type: ignore[assignment]
    yield
    _descarregar_extensoes()
