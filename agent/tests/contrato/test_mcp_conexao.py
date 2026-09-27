"""Conexão do agente com o ``bussola-mcp`` (contratos §6; AC-06, R-13).

Parte dos testes sobe o mock real (``python -m bussola_mcp.server``) num
subprocesso, em ``127.0.0.1`` e porta livre, com um diretório de fixtures
temporário. O agente não importa ``bussola_mcp``: só fala MCP pela rede local.
Nenhum teste obtém ID token real (``fetch_id_token`` é sempre substituído).
"""

import asyncio
import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.sessions.state import State
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.oauth2 import id_token
from mcp.types import CallToolResult, TextContent

from bussola_agent import mcp_conexao
from bussola_agent.estado import estado_inicial
from bussola_agent.mcp_conexao import (
    ERRO_ENTRADA_INVALIDA,
    ERRO_INDISPONIVEL,
    FERRAMENTAS_MCP,
    MSG_INDISPONIVEL,
    TIMEOUT_CHAMADA_S,
    URL_PADRAO,
    ProvedorIdToken,
    aplicar_escopo,
    audience_de,
    chamar_ferramenta,
    criar_toolset,
)

ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"
CONTROLE = "31e94f2f-1463-49f9-a41a-b3f220ed976a"
URL_CLOUD_RUN = "https://bussola-mcp-xyz.a.run.app/mcp"

RAIZ = Path(__file__).resolve().parents[3]
DIR_MCP = RAIZ / "mcp_server"
ESPERA_SERVIDOR_S = 90.0

# Argumentos mínimos válidos de cada ferramenta (além do escopo), contratos §5.
ARGS_MINIMOS: dict[str, dict[str, Any]] = {
    "perfil_financeiro": {},
    "capacidade_poupanca": {},
    "oportunidades_corte": {"top_n": 3},
    "dividas_e_parcelas": {},
    "simular_objetivo": {"valor_alvo": 30000.0, "prazo_meses": 24},
    "comparar_cenarios": {"valor_alvo": 30000.0, "prazo_meses": 24},
    "buscar_contexto_financeiro": {"pergunta": "O que é o CET?"},
    "resumo_mes": {"anomes": 202506},
    "planejar_marcos": {"valor_alvo": 300000.0, "prazo_meses": 24},
}


# ---------------------------------------------------------------------------
# Mock real em subprocesso
# ---------------------------------------------------------------------------


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _cauda(caminho: Path, linhas: int = 30) -> str:
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(sem saída)"
    return "\n".join(texto.splitlines()[-linhas:])


def _encerrar(processo: subprocess.Popen[bytes]) -> None:
    """Encerra o ``uv run`` e o Python filho (mesmo grupo de processos)."""
    if processo.poll() is not None:
        return
    for sinal, espera in ((signal.SIGTERM, 10), (signal.SIGKILL, 10)):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(processo.pid, sinal)
        try:
            processo.wait(timeout=espera)
            return
        except subprocess.TimeoutExpired:
            continue


@contextlib.contextmanager
def _mock_mcp(dir_fixtures: Path) -> Iterator[str]:
    """Sobe o mock real com ``dir_fixtures`` e devolve a URL ``/mcp``."""
    uv = shutil.which("uv")
    if uv is None or not (DIR_MCP / "bussola_mcp" / "server.py").is_file():
        pytest.skip("mock MCP indisponível: falta o uv ou mcp_server/bussola_mcp/server.py")
    porta = _porta_livre()
    ambiente = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    ambiente["PYTHONUNBUFFERED"] = "1"
    saida = dir_fixtures.parent / f"mock_{porta}.log"
    comando = [
        uv,
        "run",
        "--frozen",
        "--project",
        str(DIR_MCP),
        "python",
        "-m",
        "bussola_mcp.server",
        "--host",
        "127.0.0.1",
        "--port",
        str(porta),
        "--fixtures",
        str(dir_fixtures),
    ]
    with saida.open("wb") as arquivo:
        processo = subprocess.Popen(
            comando,
            cwd=DIR_MCP,
            env=ambiente,
            stdin=subprocess.DEVNULL,
            stdout=arquivo,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        limite = time.monotonic() + ESPERA_SERVIDOR_S
        while True:
            if processo.poll() is not None:
                pytest.fail(f"O mock MCP encerrou antes de abrir a porta:\n{_cauda(saida)}")
            try:
                socket.create_connection(("127.0.0.1", porta), timeout=0.5).close()
                break
            except OSError:
                if time.monotonic() > limite:
                    pytest.fail(f"O mock MCP não abriu a porta a tempo:\n{_cauda(saida)}")
                time.sleep(0.1)
        yield f"http://127.0.0.1:{porta}/mcp"
    finally:
        _encerrar(processo)


@pytest.fixture(scope="module")
def mock_vazio(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Mock real com diretório de fixtures vazio."""
    dir_fixtures = tmp_path_factory.mktemp("mock_vazio") / "fixtures"
    dir_fixtures.mkdir()
    with _mock_mcp(dir_fixtures) as url:
        yield url


@pytest.fixture(scope="module")
def mock_com_usuarios(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Mock real só com ``usuarios.json`` (âncora e controle), sem golden files."""
    dir_fixtures = tmp_path_factory.mktemp("mock_usuarios") / "fixtures"
    dir_fixtures.mkdir()
    usuarios = [
        {"id_usuario": ANCORA, "papel": "ancora", "faixa_renda": "faixa_teste"},
        {"id_usuario": CONTROLE, "papel": "controle", "faixa_renda": "faixa_teste"},
    ]
    (dir_fixtures / "usuarios.json").write_text(json.dumps(usuarios), encoding="utf-8")
    with _mock_mcp(dir_fixtures) as url:
        yield url


@pytest.fixture
def espiao_transporte(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Registra argumentos e resultado bruto de cada chamada real ao MCP."""
    original = mcp_conexao._chamar_mcp
    chamadas: list[dict[str, Any]] = []

    async def espiao(url: str, cabecalhos: dict[str, str], nome: str, argumentos: dict) -> Any:
        registro: dict[str, Any] = {"nome": nome, "argumentos": argumentos}
        chamadas.append(registro)
        registro["resultado"] = await original(url, cabecalhos, nome, argumentos)
        return registro["resultado"]

    monkeypatch.setattr(mcp_conexao, "_chamar_mcp", espiao)
    return chamadas


def _codigo(envelope: dict[str, Any]) -> str | None:
    erro = envelope.get("erro")
    return erro.get("codigo") if isinstance(erro, dict) else None


async def test_toolset_lista_as_ferramentas_do_servidor(mock_vazio: str) -> None:
    """AC-06: ``criar_toolset(...).get_tools()`` lista as 9 ferramentas do servidor (003).

    As 8 de ``FERRAMENTAS_MCP`` e ``referencia_coorte`` (contratos §5).
    """
    toolset = criar_toolset(url=mock_vazio)
    try:
        ferramentas = await toolset.get_tools()
    finally:
        await toolset.close()
    nomes = {f.name for f in ferramentas}
    assert set(FERRAMENTAS_MCP) <= nomes
    assert "referencia_coorte" in nomes
    assert len(ferramentas) == 10


async def test_toolset_com_filtro(mock_vazio: str) -> None:
    toolset = criar_toolset(url=mock_vazio, tool_filter=["resumo_mes", "perfil_financeiro"])
    try:
        nomes = {f.name for f in await toolset.get_tools()}
    finally:
        await toolset.close()
    assert nomes == {"resumo_mes", "perfil_financeiro"}


@pytest.mark.parametrize("ferramenta", FERRAMENTAS_MCP)
async def test_fixtures_vazias_devolvem_indisponivel_do_mock(
    ferramenta: str, mock_vazio: str, espiao_transporte: list[dict[str, Any]]
) -> None:
    """Sem fixtures o mock responde ``INDISPONIVEL`` (e ``list_tools`` segue funcionando)."""
    envelope = await chamar_ferramenta(
        ferramenta, ARGS_MINIMOS[ferramenta], estado_inicial(ANCORA, 202506), url=mock_vazio
    )
    assert _codigo(envelope) == ERRO_INDISPONIVEL
    # A resposta veio do mock (não de falha de transporte).
    [chamada] = espiao_transporte
    assert isinstance(chamada["resultado"], CallToolResult)
    assert not chamada["resultado"].isError


async def test_escopo_do_state_prevalece_no_mock_real(
    mock_com_usuarios: str, espiao_transporte: list[dict[str, Any]]
) -> None:
    """O modelo pede o âncora, mas o ``state`` é do controle: o mock vê o controle.

    Sem as tabelas no diretório de fixtures, o domínio (001) responde
    ``INDISPONIVEL`` para qualquer cliente; o que importa é o argumento enviado.
    """
    args_do_modelo = {"id_usuario": ANCORA, "ate_anomes": 202512}
    envelope = await chamar_ferramenta(
        "perfil_financeiro",
        args_do_modelo,
        estado_inicial(CONTROLE, 202506),
        url=mock_com_usuarios,
    )
    assert _codigo(envelope) == ERRO_INDISPONIVEL
    assert espiao_transporte[0]["argumentos"] == {"id_usuario": CONTROLE, "ate_anomes": 202506}
    assert args_do_modelo == {"id_usuario": ANCORA, "ate_anomes": 202512}


async def test_usuario_do_state_fora_das_fixtures(mock_com_usuarios: str) -> None:
    envelope = await chamar_ferramenta(
        "perfil_financeiro",
        {"id_usuario": ANCORA},
        estado_inicial(str(uuid.uuid4()), 202506),
        url=mock_com_usuarios,
    )
    assert _codigo(envelope) == "USUARIO_INEXISTENTE"


async def test_ancora_sem_golden_files(
    mock_com_usuarios: str, espiao_transporte: list[dict[str, Any]]
) -> None:
    envelope = await chamar_ferramenta(
        "perfil_financeiro",
        {"id_usuario": CONTROLE},
        estado_inicial(ANCORA, 202506),
        url=mock_com_usuarios,
    )
    assert _codigo(envelope) == ERRO_INDISPONIVEL
    assert espiao_transporte[0]["argumentos"]["id_usuario"] == ANCORA
    assert not espiao_transporte[0]["resultado"].isError


async def test_header_oidc_no_mock_real_com_cache(
    mock_vazio: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com OIDC, o ``McpToolset`` pede o token uma vez e reaproveita o cache."""
    pedidos: list[str] = []

    def fetch_falso(_requisicao: Any, audience: str) -> str:
        pedidos.append(audience)
        return "token-falso"

    monkeypatch.setattr(id_token, "fetch_id_token", fetch_falso)
    monkeypatch.setattr(mcp_conexao, "_provedores", {})
    toolset = criar_toolset(url=mock_vazio, usar_oidc=True)
    contexto = SimpleNamespace()  # o ADK só chama o header_provider com contexto
    try:
        primeira = await toolset.get_tools(readonly_context=contexto)
        segunda = await toolset.get_tools(readonly_context=contexto)
    finally:
        await toolset.close()
    assert len(primeira) == len(segunda) == 10
    assert pedidos == [mock_vazio.removesuffix("/mcp")]


# ---------------------------------------------------------------------------
# Sem servidor
# ---------------------------------------------------------------------------


async def test_sem_servidor_devolve_indisponivel() -> None:
    """AC-06: com o MCP fora do ar, o envelope é ``INDISPONIVEL`` (sem exceção)."""
    url = f"http://127.0.0.1:{_porta_livre()}/mcp"
    inicio = time.monotonic()
    envelope = await chamar_ferramenta(
        "perfil_financeiro", {}, estado_inicial(ANCORA, 202506), url=url
    )
    assert envelope == {"erro": {"codigo": ERRO_INDISPONIVEL, "mensagem": MSG_INDISPONIVEL}}
    assert time.monotonic() - inicio < TIMEOUT_CHAMADA_S


async def test_url_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []

    async def transporte(url: str, *_: Any) -> CallToolResult:
        urls.append(url)
        return _resultado({"dados": {}})

    monkeypatch.setattr(mcp_conexao, "_chamar_mcp", transporte)
    monkeypatch.delenv("MCP_URL", raising=False)
    await chamar_ferramenta("resumo_mes", {}, estado_inicial(ANCORA, 202506))
    monkeypatch.setenv("MCP_URL", "http://127.0.0.1:9999/mcp")
    await chamar_ferramenta("resumo_mes", {}, estado_inicial(ANCORA, 202506))
    await chamar_ferramenta("resumo_mes", {}, estado_inicial(ANCORA, 202506), url="http://x/mcp")
    assert urls == [URL_PADRAO, "http://127.0.0.1:9999/mcp", "http://x/mcp"]


# ---------------------------------------------------------------------------
# aplicar_escopo
# ---------------------------------------------------------------------------


def test_aplicar_escopo_sobrescreve_valores_do_modelo() -> None:
    args = {"id_usuario": CONTROLE, "ate_anomes": 202512, "top_n": 3}
    escopado = aplicar_escopo(args, estado_inicial(ANCORA, 202506))
    assert escopado == {"id_usuario": ANCORA, "ate_anomes": 202506, "top_n": 3}
    assert args == {"id_usuario": CONTROLE, "ate_anomes": 202512, "top_n": 3}


def test_aplicar_escopo_sem_args_e_com_state_do_adk() -> None:
    state = State(value=estado_inicial(ANCORA, 202509), delta={})
    assert aplicar_escopo(None, state) == {"id_usuario": ANCORA, "ate_anomes": 202509}
    assert aplicar_escopo({}, state) == {"id_usuario": ANCORA, "ate_anomes": 202509}


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"id_usuario": ANCORA},
        {"ate_anomes": 202506},
        {"id_usuario": "nao-e-uuid", "ate_anomes": 202506},
        {"id_usuario": ANCORA, "ate_anomes": 202601},
    ],
)
def test_aplicar_escopo_sem_state_valido_nao_usa_os_args(state: dict) -> None:
    with pytest.raises(ValueError):
        aplicar_escopo({"id_usuario": ANCORA, "ate_anomes": 202506}, state)


# ---------------------------------------------------------------------------
# chamar_ferramenta com transporte substituído
# ---------------------------------------------------------------------------


def _resultado(
    estruturado: Any = None, texto: str | None = None, erro: bool = False
) -> CallToolResult:
    if texto is None:
        texto = json.dumps(estruturado) if estruturado is not None else ""
    return CallToolResult(
        content=[TextContent(type="text", text=texto)],
        structuredContent=estruturado,
        isError=erro,
    )


@pytest.fixture
def transporte(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Substitui ``_chamar_mcp``; ``transporte.resposta`` define o retorno."""
    falso = SimpleNamespace(chamadas=[], resposta=_resultado({"dados": {"ok": 1}, "avisos": []}))

    async def chamar(url: str, cabecalhos: dict, nome: str, argumentos: dict) -> Any:
        falso.chamadas.append(
            {"url": url, "cabecalhos": cabecalhos, "nome": nome, "argumentos": argumentos}
        )
        if isinstance(falso.resposta, BaseException):
            raise falso.resposta
        return falso.resposta

    monkeypatch.setattr(mcp_conexao, "_chamar_mcp", chamar)
    return falso


async def test_chamada_envia_escopo_e_devolve_envelope(transporte: SimpleNamespace) -> None:
    envelope = await chamar_ferramenta(
        "oportunidades_corte",
        {"id_usuario": CONTROLE, "top_n": 3},
        estado_inicial(ANCORA, 202506),
        url="http://127.0.0.1:1/mcp",
    )
    assert envelope == {"dados": {"ok": 1}, "avisos": []}
    [chamada] = transporte.chamadas
    assert chamada["nome"] == "oportunidades_corte"
    assert chamada["argumentos"] == {"id_usuario": ANCORA, "ate_anomes": 202506, "top_n": 3}
    assert chamada["cabecalhos"] == {}


@pytest.mark.parametrize(
    "resposta",
    [
        _resultado({"result": {"dados": {"ok": 1}, "avisos": []}}),
        _resultado(None, texto=json.dumps({"dados": {"ok": 1}, "avisos": []})),
    ],
    ids=["result_embrulhado", "so_texto"],
)
async def test_formatos_de_resposta_aceitos(
    transporte: SimpleNamespace, resposta: CallToolResult
) -> None:
    transporte.resposta = resposta
    envelope = await chamar_ferramenta("perfil_financeiro", {}, estado_inicial(ANCORA, 202506))
    assert envelope == {"dados": {"ok": 1}, "avisos": []}


async def test_erro_de_negocio_volta_como_veio(transporte: SimpleNamespace) -> None:
    erro = {"erro": {"codigo": "USUARIO_INEXISTENTE", "mensagem": "Cliente não encontrado."}}
    transporte.resposta = _resultado(erro)
    assert await chamar_ferramenta("resumo_mes", {}, estado_inicial(ANCORA, 202506)) == erro


@pytest.mark.parametrize(
    "resposta",
    [
        _resultado(None, texto="Error executing tool", erro=True),
        _resultado({"dados": {}}, erro=True),
        _resultado(None, texto="texto que não é JSON"),
        _resultado({"outra": "coisa"}),
        ExceptionGroup("falha de transporte", [ConnectionError("recusada")]),
        RuntimeError("erro de protocolo"),
    ],
    ids=["is_error", "is_error_com_envelope", "nao_json", "fora_do_contrato", "grupo", "runtime"],
)
async def test_falhas_viram_indisponivel(transporte: SimpleNamespace, resposta: Any) -> None:
    transporte.resposta = resposta
    envelope = await chamar_ferramenta("resumo_mes", {}, estado_inicial(ANCORA, 202506))
    assert envelope == {"erro": {"codigo": ERRO_INDISPONIVEL, "mensagem": MSG_INDISPONIVEL}}


async def test_timeout_vira_indisponivel(monkeypatch: pytest.MonkeyPatch) -> None:
    async def lento(*_: Any) -> CallToolResult:
        await asyncio.sleep(5)
        return _resultado({"dados": {}})

    monkeypatch.setattr(mcp_conexao, "_chamar_mcp", lento)
    monkeypatch.setattr(mcp_conexao, "TIMEOUT_CHAMADA_S", 0.05)
    envelope = await chamar_ferramenta("resumo_mes", {}, estado_inicial(ANCORA, 202506))
    assert _codigo(envelope) == ERRO_INDISPONIVEL


@pytest.mark.parametrize("state", [{}, {"id_usuario": "nao-e-uuid", "ate_anomes": 202506}])
async def test_state_invalido_da_entrada_invalida_sem_chamar(
    transporte: SimpleNamespace, state: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    envelope = await chamar_ferramenta("perfil_financeiro", {"id_usuario": ANCORA}, state)
    assert _codigo(envelope) == ERRO_ENTRADA_INVALIDA
    assert "nao-e-uuid" not in json.dumps(envelope, ensure_ascii=False)
    assert transporte.chamadas == []
    assert "nao-e-uuid" not in capsys.readouterr().out


async def test_log_da_chamada_so_com_campos_permitidos(
    transporte: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    await chamar_ferramenta("resumo_mes", {"anomes": 202506}, estado_inicial(ANCORA, 202506))
    linhas = [json.loads(linha) for linha in capsys.readouterr().out.splitlines() if linha]
    [linha] = [x for x in linhas if x.get("evento") == "mcp_chamada"]
    assert linha["ferramenta"] == "resumo_mes"
    assert linha["ate_anomes"] == 202506
    assert isinstance(linha["latencia_ms"], int)
    assert "erro_codigo" not in linha


# ---------------------------------------------------------------------------
# OIDC
# ---------------------------------------------------------------------------


@pytest.fixture
def fetch_falso(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Substitui ``fetch_id_token``; devolve a lista de ``audience`` pedidas."""
    pedidos: list[str] = []

    def fetch(_requisicao: Any, audience: str) -> str:
        pedidos.append(audience)
        return f"token-secreto-{len(pedidos)}"

    monkeypatch.setattr(id_token, "fetch_id_token", fetch)
    monkeypatch.setattr(mcp_conexao, "_provedores", {})
    return pedidos


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        (URL_CLOUD_RUN, "https://bussola-mcp-xyz.a.run.app"),
        ("http://localhost:8080/mcp", "http://localhost:8080"),
        ("http://127.0.0.1:9000/mcp?x=1", "http://127.0.0.1:9000"),
        ("http://[::1]:8080/mcp", "http://[::1]:8080"),
    ],
)
def test_audience_e_a_url_base(url: str, esperado: str) -> None:
    assert audience_de(url) == esperado


@pytest.mark.parametrize("url", ["", "localhost:8080/mcp", "ftp://host/mcp", "https:///mcp"])
def test_audience_de_url_invalida(url: str) -> None:
    with pytest.raises(ValueError):
        audience_de(url)


def test_provedor_cacheia_e_renova(fetch_falso: list[str]) -> None:
    agora = [1000.0]
    provedor = ProvedorIdToken(
        "https://bussola-mcp-xyz.a.run.app", ttl_s=60, relogio=lambda: agora[0]
    )
    assert provedor() == {"Authorization": "Bearer token-secreto-1"}
    agora[0] += 59
    assert provedor(SimpleNamespace()) == {"Authorization": "Bearer token-secreto-1"}
    agora[0] += 1
    assert provedor() == {"Authorization": "Bearer token-secreto-2"}
    assert fetch_falso == ["https://bussola-mcp-xyz.a.run.app"] * 2
    assert "token-secreto" not in repr(provedor)


def test_ttl_padrao_de_45_minutos() -> None:
    assert mcp_conexao.TTL_TOKEN_S == 45 * 60
    assert ProvedorIdToken("https://x").ttl_s == 45 * 60


def test_toolset_sem_oidc_por_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_URL", raising=False)
    toolset = criar_toolset()
    assert isinstance(toolset, McpToolset)
    assert toolset.connection_params.url == URL_PADRAO
    assert toolset.connection_params.timeout == TIMEOUT_CHAMADA_S
    assert toolset.header_provider is None


def test_toolset_com_oidc_pelo_ambiente(
    monkeypatch: pytest.MonkeyPatch, fetch_falso: list[str]
) -> None:
    monkeypatch.setenv("MCP_USE_OIDC", "true")
    monkeypatch.setenv("MCP_URL", URL_CLOUD_RUN)
    toolset = criar_toolset()
    assert toolset.connection_params.url == URL_CLOUD_RUN
    provedor = toolset.header_provider
    assert isinstance(provedor, ProvedorIdToken)
    assert provedor.audience == "https://bussola-mcp-xyz.a.run.app"
    assert fetch_falso == []  # criar o toolset não busca token
    assert criar_toolset(usar_oidc=False).header_provider is None
    assert criar_toolset().header_provider is provedor  # mesmo cache por audience


def test_toolset_oidc_com_url_invalida() -> None:
    with pytest.raises(ValueError):
        criar_toolset(url="localhost/mcp", usar_oidc=True)


async def test_chamada_direta_com_oidc(
    transporte: SimpleNamespace, fetch_falso: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    state = estado_inicial(ANCORA, 202506)
    for _ in range(2):
        await chamar_ferramenta("resumo_mes", {}, state, url=URL_CLOUD_RUN, usar_oidc=True)
    assert [c["cabecalhos"] for c in transporte.chamadas] == [
        {"Authorization": "Bearer token-secreto-1"}
    ] * 2
    assert fetch_falso == ["https://bussola-mcp-xyz.a.run.app"]
    assert "token-secreto" not in capsys.readouterr().out


async def test_falha_ao_obter_token_vira_indisponivel(
    transporte: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sem_credenciais(*_: Any) -> str:
        raise RuntimeError("sem credenciais")

    monkeypatch.setattr(id_token, "fetch_id_token", sem_credenciais)
    monkeypatch.setattr(mcp_conexao, "_provedores", {})
    envelope = await chamar_ferramenta(
        "resumo_mes", {}, estado_inicial(ANCORA, 202506), url=URL_CLOUD_RUN, usar_oidc=True
    )
    assert _codigo(envelope) == ERRO_INDISPONIVEL
    assert transporte.chamadas == []
