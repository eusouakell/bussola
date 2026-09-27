"""Fakes do 006 para testes e eval offline (``BUSSOLA_FAKES=TRUE``), sem rede e sem GCP.

- :class:`FixtureMcp` responde ``resumo_mes`` e ``simular_objetivo`` a partir
  de ``contracts/fixtures/`` com as regras do mock do 000 (``resumo_mes`` exige
  ``anomes <= ate_anomes``; ``simular_objetivo`` devolve o golden do corte). Só
  o âncora tem golden gravado, mas isso não é falta de histórico: como no
  ``golden_adapter`` do MCP, ``DADOS_INSUFICIENTES`` fica reservado a quem não
  tem nenhum mês de ``perfil_mensal`` até o corte (BUG-05); os outros clientes
  recebem o mesmo envelope de exemplo, que é o que os testes offline precisam.
  Com ``canned=False``, ``simular_objetivo`` é calculado para a entrada
  (comportamento esperado do 003).
- :class:`FixtureMcpGateway` implementa a porta :class:`~.ports.McpGateway`.
- :func:`fake_transport` substitui ``mcp_conexao._chamar_mcp`` e devolve um
  ``CallToolResult`` como o do servidor real (``structuredContent`` + JSON).
- :class:`ScriptedLlm` é um ``BaseLlm`` roteirizado para o ``InMemoryRunner``.
- :func:`plan_state` e :func:`tool_context` montam a sessão de um plano ativo
  (como o 004/005 deixam) para testes e eval.
- :func:`command_router` e :func:`render_tool_answer` são o "cérebro"
  determinístico do :class:`ScriptedLlm`: comando do cliente vira chamada de
  ferramenta, e a resposta usa só os números devolvidos pela ferramenta.
- :func:`install_journey` registra a composição real: consentimento e
  governança do 005, acompanhamento do 006 e as cadeias do 004.
- :func:`build_conversation` monta o agente como o ``root_agent`` do 004
  (prompt base + extensões, ferramentas locais e das extensões e os 4
  agregados) num ``InMemoryRunner`` com o :class:`ScriptedLlm`;
  :class:`Conversation` roda os turnos. É o mesmo arnês na integração e no
  eval.
"""

import copy
import json
import re
from collections.abc import AsyncGenerator, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from google.adk.agents import Agent
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from mcp.types import CallToolResult, TextContent
from pydantic import Field

import bussola_agent
from bussola_agent import callbacks, extensoes, mcp_conexao
from bussola_agent.acompanhamento.money import format_brl, format_months
from bussola_agent.acompanhamento.ports import TOOL_MONTHLY_SUMMARY, TOOL_SIMULATE_GOAL
from bussola_agent.acompanhamento.routes import SimulationRequest, simulate_locally
from bussola_agent.acompanhamento.tools import GOVERNANCE_PACKAGE
from bussola_agent.estado import (
    ANOMES_MAX,
    CHAVE_CENARIO_ESCOLHIDO,
    CHAVE_CENARIOS,
    CHAVE_OBJETIVO,
    CHAVE_PLANO_ID,
    anomes_valido,
    estado_inicial,
    id_usuario_valido,
)

FIXTURES_DIR = Path(bussola_agent.__file__).resolve().parents[2] / "contracts" / "fixtures"
PARTIAL_CUT = 202506
CANNED_INPUT = {"valor_alvo": 30000.0, "prazo_meses": 24}
ANCHOR_USER_ID = "36a21505-d6d4-42d3-b319-d51a133c7269"
CONTROL_USER_ID = "31e94f2f-1463-49f9-a41a-b3f220ed976a"

_MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def month_label(anomes: int) -> str:
    """``202506`` → ``"junho/2025"``: mesmo texto do ``golden_adapter`` do MCP."""
    return f"{_MONTHS[anomes % 100 - 1]}/{anomes // 100}"


WARNING_DEMO_PREFIX = "Exemplo desta demonstração:"
"""Prefixo estável dos avisos de dado gravado, igual ao do MCP (BUG-06)."""

WARNING_DEMO_CUT = f"{WARNING_DEMO_PREFIX} números com dados até {month_label(PARTIAL_CUT)}."
WARNING_DEMO_SIMULATION = (
    f"{WARNING_DEMO_PREFIX} simulação para uma meta de "
    f"{format_brl(CANNED_INPUT['valor_alvo'])} "
    f"em {format_months(int(CANNED_INPUT['prazo_meses']))}."
)

_MESSAGES = {
    "ENTRADA_INVALIDA": "Entrada inválida.",
    "USUARIO_INEXISTENTE": "Cliente não encontrado.",
    "DADOS_INSUFICIENTES": "Ainda não tenho nenhum mês de histórico até esta data.",
    "PRAZO_IMPLAUSIVEL": "Prazo implausível para o objetivo informado.",
    "INDISPONIVEL": "Dados de exemplo indisponíveis.",
}


def _error(code: str) -> dict[str, Any]:
    return {"erro": {"codigo": code, "mensagem": _MESSAGES.get(code, _MESSAGES["INDISPONIVEL"])}}


@dataclass
class FixtureMcp:
    """Espelho das regras do mock do 000 para ``resumo_mes`` e ``simular_objetivo``."""

    fixtures_dir: Path = FIXTURES_DIR
    canned: bool = True
    fail_tools: dict[str, str] = field(default_factory=dict)
    fail_months: dict[int, str] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def _users(self) -> dict[str, str]:
        items = json.loads((self.fixtures_dir / "usuarios.json").read_text(encoding="utf-8"))
        return {item["id_usuario"]: item["papel"] for item in items}

    def _months(self, user_id: str, cut: int) -> list[int]:
        """Meses de ``perfil_mensal`` do cliente até o corte (regra honesta do domínio)."""
        path = self.fixtures_dir / "bussola_dados" / "perfil_mensal.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        return sorted(
            row["anomes"]
            for row in rows
            if row["id_usuario"].lower() == user_id.lower() and row["anomes"] <= cut
        )

    def _load(self, name: str) -> dict[str, Any]:
        path = self.fixtures_dir / "ferramentas" / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def call(self, tool: str, args: Mapping[str, Any]) -> dict[str, Any]:
        """Envelope §5 para ``tool`` com ``args`` (já com o escopo)."""
        self.calls.append((tool, copy.deepcopy(dict(args))))
        if tool in self.fail_tools:
            return _error(self.fail_tools[tool])
        user_id, cut = args.get("id_usuario"), args.get("ate_anomes")
        if not id_usuario_valido(user_id) or not anomes_valido(cut):
            return _error("ENTRADA_INVALIDA")
        role = self._users().get(str(user_id).lower())
        if role is None:
            return _error("USUARIO_INEXISTENTE")
        if not self._months(str(user_id), int(cut)):
            return _error("DADOS_INSUFICIENTES")
        if tool == TOOL_MONTHLY_SUMMARY:
            return self._monthly_summary(args, cut)
        if tool == TOOL_SIMULATE_GOAL:
            return self._simulate_goal(args, cut)
        return _error("INDISPONIVEL")

    def _monthly_summary(self, args: Mapping[str, Any], cut: int) -> dict[str, Any]:
        month = args.get("anomes")
        if not anomes_valido(month) or month > cut:
            return _error("ENTRADA_INVALIDA")
        if month in self.fail_months:
            return _error(self.fail_months[month])
        return self._load(f"resumo_mes__{month}")

    def _simulate_goal(self, args: Mapping[str, Any], cut: int) -> dict[str, Any]:
        term, contribution = args.get("prazo_meses"), args.get("aporte_mensal")
        target = args.get("valor_alvo")
        if (term is None) == (contribution is None) or not isinstance(target, int | float):
            return _error("ENTRADA_INVALIDA")
        golden_cut = PARTIAL_CUT if cut < ANOMES_MAX else ANOMES_MAX
        envelope = self._load(f"simular_objetivo__ate_{golden_cut}")
        warnings = [WARNING_DEMO_CUT] if golden_cut == PARTIAL_CUT else []
        if self.canned:
            warnings.append(WARNING_DEMO_SIMULATION)
        else:
            premises = envelope["dados"]["premissas"]
            try:
                envelope["dados"] = simulate_locally(
                    SimulationRequest(float(target), term_months=term, contribution=contribution),
                    float(premises["capacidade_mensal"]),
                    premises,
                )
            except ValueError:
                return _error("PRAZO_IMPLAUSIVEL")
        envelope["avisos"] = [*envelope.get("avisos", []), *warnings]
        return envelope


class FixtureMcpGateway:
    """Porta :class:`~.ports.McpGateway` sobre um :class:`FixtureMcp` (escopo do state)."""

    def __init__(self, mcp: FixtureMcp | None = None) -> None:
        self.mcp = mcp or FixtureMcp()

    async def monthly_summary(self, anomes: int, state: Mapping[str, Any]) -> dict[str, Any]:
        return self._call(TOOL_MONTHLY_SUMMARY, {"anomes": anomes}, state)

    async def simulate_goal(
        self,
        valor_alvo: float,
        state: Mapping[str, Any],
        prazo_meses: int | None = None,
        aporte_mensal: float | None = None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {"valor_alvo": valor_alvo}
        if prazo_meses is not None:
            args["prazo_meses"] = prazo_meses
        if aporte_mensal is not None:
            args["aporte_mensal"] = aporte_mensal
        return self._call(TOOL_SIMULATE_GOAL, args, state)

    def _call(self, tool: str, args: dict[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
        try:
            scoped = mcp_conexao.aplicar_escopo(args, state)
        except ValueError:
            return {
                "erro": {
                    "codigo": mcp_conexao.ERRO_ENTRADA_INVALIDA,
                    "mensagem": mcp_conexao.MSG_ESCOPO_INVALIDO,
                }
            }
        return self.mcp.call(tool, scoped)


def fake_transport(
    mcp: FixtureMcp,
) -> Callable[[str, dict[str, str], str, dict[str, Any]], Any]:
    """Substituto de ``mcp_conexao._chamar_mcp`` que responde com o :class:`FixtureMcp`."""

    async def _call(
        url: str, headers: dict[str, str], name: str, arguments: dict[str, Any]
    ) -> CallToolResult:
        envelope = mcp.call(name, arguments)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(envelope, ensure_ascii=False))],
            structuredContent=envelope,
            isError=False,
        )

    return _call


# ---------------------------------------------------------------------------
# Sessão com plano ativo
# ---------------------------------------------------------------------------


def plan_state(
    user_id: str = ANCHOR_USER_ID,
    ate_anomes: int = PARTIAL_CUT,
    *,
    valor_alvo: float = 60000.0,
    aporte_mensal: float = 2500.0,
    prazo_meses: int = 24,
    cenario: str = "equilibrado",
    plano_id: str | None = "plano-inicial",
) -> dict[str, Any]:
    """``session.state`` com objetivo, cenário escolhido e ``plano_id`` (chaves §6).

    É o que o 004 (objetivo e cenários) e o 005 (``plano_id``) deixam na
    sessão depois de ``criar_plano``. Com ``plano_id=None``, não há plano.
    """
    state = estado_inicial(user_id, ate_anomes)
    state[CHAVE_OBJETIVO] = {
        "tipo": "reserva",
        "descricao": "Reserva de emergência",
        "valor_alvo": valor_alvo,
        "prazo_meses": prazo_meses,
        "prioridade": "alta",
    }
    state[CHAVE_CENARIOS] = {
        "cenarios": [
            {"nome": cenario, "aporte_mensal": aporte_mensal, "prazo_meses": prazo_meses},
        ]
    }
    state[CHAVE_CENARIO_ESCOLHIDO] = cenario
    state[CHAVE_PLANO_ID] = plano_id
    return state


def tool_context(state: dict[str, Any], session_id: str = "sessao-006") -> Any:
    """``ToolContext`` mínimo (``state`` e ``session.id``) para chamar as ferramentas direto."""
    return SimpleNamespace(state=state, session=SimpleNamespace(id=session_id))


# ---------------------------------------------------------------------------
# LLM roteirizado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Call:
    """Passo do roteiro: o modelo chama a ferramenta ``name`` com ``args``."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)


Step = str | Call | Callable[[LlmRequest], "str | Call"]


def last_function_response(request: LlmRequest) -> tuple[str, dict[str, Any]] | None:
    """Nome e resposta da última ``function_response`` do pedido, se houver."""
    for content in reversed(request.contents or []):
        for part in reversed(content.parts or []):
            if part.function_response is not None:
                response = part.function_response.response or {}
                return part.function_response.name or "", dict(response)
    return None


class ScriptedLlm(BaseLlm):
    """``BaseLlm`` que devolve os passos do roteiro, um por chamada ao modelo.

    Um passo é um texto, um :class:`Call` ou uma função que recebe o
    ``LlmRequest`` e devolve um dos dois. Sem passos, responde um texto
    neutro. ``requests`` guarda os pedidos, para as asserções dos testes.
    """

    model: str = "falso-roteirizado"
    script: list[Any] = Field(default_factory=list)
    requests: list[Any] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.requests.append(llm_request)
        step: Any = self.script.pop(0) if self.script else "Tudo certo."
        if callable(step) and not isinstance(step, Call):
            step = step(llm_request)
        if isinstance(step, Call):
            part = types.Part(function_call=types.FunctionCall(name=step.name, args=step.args))
        else:
            part = types.Part(text=str(step))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


# ---------------------------------------------------------------------------
# "Cérebro" determinístico do ScriptedLlm
# ---------------------------------------------------------------------------

ADVANCE_COMMANDS = ("avançar um mês", "avancar um mes", "próximo mês")
STATUS_COMMANDS = ("ver status do plano", "status do plano")
_STATUS_TEXT = {
    "desvio": "abaixo do planejado",
    "no_plano": "dentro do plano",
    "folga": "acima do planejado",
}


def last_user_text(request: LlmRequest) -> str:
    """Último texto escrito pelo cliente no pedido ao modelo ("" se não houver)."""
    for content in reversed(request.contents or []):
        if content.role != "user":
            continue
        texts = [p.text for p in content.parts or [] if p.text and not p.thought]
        if texts:
            return " ".join(texts).strip()
    return ""


def command_router(request: LlmRequest) -> "Call | str":
    """Comando do front (``TEXTO_AVANCAR`` e "Ver status do plano") vira chamada de ferramenta."""
    text = last_user_text(request).casefold().rstrip(".!")
    if text in ADVANCE_COMMANDS:
        return Call("avancar_mes")
    if text in STATUS_COMMANDS:
        return Call("status_plano")
    return "Posso avançar um mês ou mostrar o status do plano."


def _month_name(anomes: Any) -> str:
    if isinstance(anomes, int) and 1 <= anomes % 100 <= 12:
        return f"{_MONTHS[anomes % 100 - 1]} de {anomes // 100}"
    return "o mês revelado"


def _percent(value: float) -> str:
    return f"{value:.2f}".replace(".", ",") + "%"


def _answer_advance(dados: Mapping[str, Any]) -> str:
    lines = [
        f"**O que aconteceu:** em {_month_name(dados.get('anomes'))}, o planejado era "
        f"{format_brl(dados['planejado'])} e o realizado foi {format_brl(dados['realizado'])} "
        f"({_STATUS_TEXT.get(dados['status'], dados['status'])}). Você acumulou "
        f"{format_brl(dados['acumulado'])} ({_percent(dados['percentual'])} da meta)."
    ]
    category = dados.get("categoria_desvio")
    if isinstance(category, Mapping):
        lines.append(
            f"**Por quê:** {category['macro']} somou {format_brl(category['valor_mes'])}, "
            f"contra uma média de {format_brl(category['media_base'])} antes do plano."
        )
    routes = dados.get("rotas") or []
    if routes:
        options = []
        for route in routes:
            text = (
                f"rota {route['id']} ({route['titulo'].lower()}): "
                f"{format_brl(route['aporte_mensal'])} por mês durante "
                f"{format_months(route['prazo_meses'])}"
            )
            if route["simulacao"]["dados"].get("viavel") is False:
                text += ", acima da capacidade mensal estimada"
            options.append(text)
        lines.append("**O que fazer (simulação):** " + "; ".join(options) + ".")
    elif dados["status"] == "folga":
        lines.append("Você pode manter o plano ou antecipar a meta, se quiser.")
    else:
        lines.append("O plano segue bem.")
    return "\n\n".join(lines)


def _answer_status(dados: Mapping[str, Any]) -> str:
    return (
        f"Seu plano está em {_percent(dados['percentual'])} da meta: "
        f"{format_brl(dados['acumulado'])} acumulados e faltam "
        f"{format_brl(dados['restante'])} em {format_months(dados['meses_restantes'])}."
    )


def render_tool_answer(request: LlmRequest) -> str:
    """Resposta em pt-BR montada só com os números da última ferramenta chamada."""
    last = last_function_response(request)
    if last is None:
        return "Tudo certo."
    name, envelope = last
    erro = envelope.get("erro")
    if isinstance(erro, Mapping):
        return str(erro.get("mensagem") or "Não foi possível agora.")
    dados = envelope.get("dados") or {}
    if name == "avancar_mes":
        return _answer_advance(dados)
    if name == "status_plano":
        return _answer_status(dados)
    if name == "ajustar_plano":
        return str(dados.get("mensagem"))
    if name == "solicitar_consentimento":
        return (
            "Para ajustar o plano, preciso da sua autorização. Posso seguir? Responda sim ou não."
        )
    return "Tudo certo."


_AMOUNT_RE = re.compile(r"R\$ (-?[\d.]+,\d{2})")
_PERCENT_RE = re.compile(r"(\d+,\d{2})%")
_MONTHS_RE = re.compile(r"(\d+) m[eê]s(?:es)?")


def numbers_in_text(text: str) -> list[float]:
    """Valores em reais, percentuais e quantidades de meses citados no texto."""
    values = [float(v.replace(".", "").replace(",", ".")) for v in _AMOUNT_RE.findall(text)]
    values += [float(v.replace(",", ".")) for v in _PERCENT_RE.findall(text)]
    values += [float(v) for v in _MONTHS_RE.findall(text)]
    return values


def numbers_in(value: Any) -> set[float]:
    """Todos os números de um envelope (recursivo)."""
    if isinstance(value, bool):
        return set()
    if isinstance(value, int | float):
        return {round(float(value), 2)}
    if isinstance(value, Mapping):
        return set().union(*(numbers_in(v) for v in value.values())) if value else set()
    if isinstance(value, list | tuple):
        return set().union(*(numbers_in(v) for v in value)) if value else set()
    return set()


# ---------------------------------------------------------------------------
# Composição da jornada (004 + 005 + 006)
# ---------------------------------------------------------------------------


def install_journey(*, governance: bool = True) -> None:
    """Registra a composição de produção depois de ``callbacks.limpar()``.

    Mesma ordem do primeiro import de ``bussola_agent.agent``: os pacotes de
    extensão (005, se ``governance``, e 006) e depois as cadeias do 004
    (``registrar_callbacks``). Com ``governance=False`` o chamador tira o 005
    de ``sys.modules``, e o ``ajustar_plano`` usa a guarda local.
    """
    import importlib

    from bussola_agent import acompanhamento
    from bussola_agent.agent import registrar_callbacks

    if governance:
        importlib.import_module(GOVERNANCE_PACKAGE).register()
    acompanhamento.register()
    registrar_callbacks()


# ---------------------------------------------------------------------------
# Arnês de conversa (InMemoryRunner + ScriptedLlm)
# ---------------------------------------------------------------------------

APP_NAME = "bussola_agent"
USER_NAME = "cliente-006"


@dataclass
class Turn:
    """Um turno: texto final, respostas de ferramentas e ``session.state`` ao fim."""

    text: str = ""
    responses: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)


class Conversation:
    """Sessão do ``InMemoryRunner`` guiada pelo roteiro do :class:`ScriptedLlm`."""

    def __init__(self, llm: ScriptedLlm, runner: InMemoryRunner, session_id: str) -> None:
        self.llm = llm
        self.runner = runner
        self.session_id = session_id

    async def say(self, text: str, *steps: Step) -> Turn:
        """Envia ``text`` como o cliente; ``steps`` são as respostas do modelo no turno."""
        self.llm.script.extend(steps)
        message = types.Content(role="user", parts=[types.Part(text=text)])
        turn = Turn()
        async for event in self.runner.run_async(
            user_id=USER_NAME, session_id=self.session_id, new_message=message
        ):
            for part in (event.content.parts or []) if event.content else []:
                if part.function_response is not None:
                    response = dict(part.function_response.response or {})
                    turn.responses.append((part.function_response.name or "", response))
                elif part.text and event.is_final_response():
                    turn.text += part.text
        session = await self.runner.session_service.get_session(
            app_name=APP_NAME, user_id=USER_NAME, session_id=self.session_id
        )
        turn.state = dict(session.state) if session is not None else {}
        if self.llm.script:
            raise AssertionError("o roteiro do modelo não foi consumido no turno")
        return turn


async def build_conversation(state: dict[str, Any]) -> Conversation:
    """Agente montado como o ``root_agent`` do 004, com o :class:`ScriptedLlm`, sobre ``state``.

    Instrução, ferramentas locais da jornada, ferramentas das extensões e os 4
    agregados de callbacks são os de produção; só o ``McpToolset`` fica de
    fora (as ferramentas do 006 chamam o MCP por ``mcp_conexao``).
    """
    from bussola_agent import prompts
    from bussola_agent.agent import inicializar_sessao
    from bussola_agent.jornada.tools import escolher_cenario, registrar_objetivo

    llm = ScriptedLlm()
    agent = Agent(
        name="bussola_acompanhamento_offline",
        model=llm,
        instruction=prompts.build_instruction(extensoes.instrucoes()),
        tools=[registrar_objetivo, escolher_cenario, *extensoes.ferramentas()],
        before_agent_callback=inicializar_sessao,
        before_model_callback=callbacks.before_model,
        after_model_callback=callbacks.after_model,
        before_tool_callback=callbacks.before_tool,
        after_tool_callback=callbacks.after_tool,
    )
    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_NAME, state=state
    )
    return Conversation(llm, runner, session.id)


def periods_in(envelope: Any) -> list[int]:
    """Todos os AAAAMM de ``anomes`` e ``periodo`` num envelope (recursivo)."""
    found: list[int] = []
    if isinstance(envelope, Mapping):
        for key, value in envelope.items():
            if key == "anomes" and isinstance(value, int):
                found.append(value)
            elif key == "periodo" and isinstance(value, Mapping):
                found += [v for v in value.values() if isinstance(v, int)]
            else:
                found += periods_in(value)
    elif isinstance(envelope, list):
        for value in envelope:
            found += periods_in(value)
    return found


def unbacked_numbers(turn: Turn) -> list[float]:
    """Números do texto final que não aparecem em nenhuma resposta de ferramenta do turno."""
    allowed = set().union(*(numbers_in(r) for _, r in turn.responses)) if turn.responses else set()
    return sorted(set(numbers_in_text(turn.text)) - allowed)
