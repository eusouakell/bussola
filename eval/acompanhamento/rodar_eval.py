"""Eval offline do acompanhamento com replay temporal (ciclo 006, FR-014).

Roda a conversa do cliente âncora no ``InMemoryRunner`` do ADK com o LLM
roteirizado de :mod:`bussola_agent.acompanhamento.fakes` e o MCP de fixtures
(``contracts/fixtures/``). Não acessa a rede, o GCP nem modelos reais.

Verifica, conforme a seção 3.7 do ciclo:

1. plano criado em 202506 (60 mil em 24 meses);
2. ``avancar_mes`` para 202507, 202508 e 202509 (e segue até 202512);
3. em cada mês, o status bate com ``desvio.py`` calculado direto sobre os
   fixtures, sem passar pela ferramenta;
4. nenhuma ferramenta devolve dado depois do ``ate_anomes`` corrente.

Também confere o ajuste com consentimento, a auditoria, a fidelidade numérica
do texto final e os casos de borda (fim do replay, sem plano, cliente de
controle, ajuste sem consentimento).

Uso: ``make eval-acompanhamento`` (ou ``cd agent && uv run python
../eval/acompanhamento/rodar_eval.py``). Grava ``resultado.md`` e
``RESULTADOS.md`` ao lado deste arquivo e sai com código 1 se alguma
verificação falhar.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bussola_agent.agent  # noqa: F401  (efeitos do primeiro import antes de fixar os registros)
from bussola_agent import callbacks, extensoes, mcp_conexao, persistencia_bq
from bussola_agent.acompanhamento import ports
from bussola_agent.acompanhamento.desvio import compute_deviation
from bussola_agent.acompanhamento.envelopes import WARNING_LOCAL_ROUTE
from bussola_agent.acompanhamento.fakes import (
    ANCHOR_USER_ID,
    CONTROL_USER_ID,
    FIXTURES_DIR,
    Call,
    FixtureMcp,
    Turn,
    build_conversation,
    command_router,
    fake_transport,
    install_journey,
    numbers_in_text,
    periods_in,
    plan_state,
    render_tool_answer,
    unbacked_numbers,
)
from bussola_agent.acompanhamento.money import format_brl, money
from bussola_agent.acompanhamento.tools import GOVERNANCE_PACKAGE
from bussola_agent.governanca import services
from bussola_agent.governanca.guardrails import RuleScreener
from bussola_agent.logging_json import configurar_logging
from bussola_agent.persistencia import RegistroEmMemoria

EVAL_DIR = Path(__file__).resolve().parent
PLAN_START = 202506
TARGET = 60000.0
INITIAL_CONTRIBUTION = 2500.0
TERM = 24
ADVANCE = "avançar um mês"
STATUS = "Ver status do plano"


@dataclass
class Check:
    """Uma verificação do eval."""

    name: str
    expected: str
    obtained: str
    ok: bool


@dataclass
class MonthRow:
    """Um mês revelado no roteiro principal."""

    anomes: int
    planned: float
    realized: float
    deviation: float
    status: str
    expected_status: str
    accumulated: float
    percent: float
    category: str | None
    routes: str
    local_routes: bool


@dataclass
class Report:
    """Resultado completo do eval."""

    months: list[MonthRow] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    answers: list[tuple[str, str]] = field(default_factory=list)
    events: dict[str, int] = field(default_factory=dict)
    tool_calls: int = 0
    envelopes: int = 0
    cited_numbers: int = 0

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def check(self, name: str, expected: Any, obtained: Any) -> None:
        self.checks.append(Check(name, str(expected), str(obtained), expected == obtained))


def fixture_sobra(anomes: int) -> float:
    """``sobra`` do mês lida direto do fixture, sem passar pela ferramenta."""
    path = FIXTURES_DIR / "ferramentas" / f"resumo_mes__{anomes}.json"
    return float(json.loads(path.read_text(encoding="utf-8"))["dados"]["sobra"])


@contextmanager
def offline_session(*, governance: bool = True) -> Iterator[tuple[FixtureMcp, Any]]:
    """Composição real (004 + 005 + 006), registro do processo em memória e MCP de fixtures.

    O guardrail de entrada usa só as regras locais (sem Model Armor). Com
    ``governance=False``, o pacote do 005 sai de ``sys.modules`` durante a
    sessão, para medir a guarda local do ``ajustar_plano``. Ao sair, restaura
    o transporte MCP, os registros, os serviços do 005 e ``sys.modules``.
    """
    fixture_mcp = FixtureMcp()
    registry = RegistroEmMemoria()
    original_transport = mcp_conexao._chamar_mcp
    governance_module = sys.modules.get(GOVERNANCE_PACKAGE)
    callbacks.limpar()
    extensoes.limpar()
    if not governance:
        sys.modules.pop(GOVERNANCE_PACKAGE, None)
    install_journey(governance=governance)
    ports.reset()
    persistencia_bq.set_default_registry(registry)
    services.configure(screener=RuleScreener())
    mcp_conexao._chamar_mcp = fake_transport(fixture_mcp)
    try:
        yield fixture_mcp, registry
    finally:
        mcp_conexao._chamar_mcp = original_transport
        if governance_module is not None:
            sys.modules[GOVERNANCE_PACKAGE] = governance_module
        ports.reset()
        services.reset()
        persistencia_bq.set_default_registry(None)
        callbacks.limpar()
        extensoes.limpar()


def _who(user_id: Any) -> str:
    return {ANCHOR_USER_ID: "âncora", CONTROL_USER_ID: "controle"}.get(user_id, "outro")


def _first(turn: Turn) -> dict[str, Any]:
    return turn.responses[0][1] if turn.responses else {}


def _audit_turn(report: Report, turn: Turn) -> None:
    """Corte temporal e fidelidade numérica de um turno."""
    cut = turn.state.get("ate_anomes")
    for _, envelope in turn.responses:
        report.envelopes += 1
        late = [p for p in periods_in(envelope) if p > cut]
        if late:
            report.check("Nenhum período depois do corte", f"<= {cut}", late)
    cited = numbers_in_text(turn.text)
    report.cited_numbers += len(cited)
    unbacked = unbacked_numbers(turn)
    if unbacked:
        report.check("Números do texto vêm das ferramentas", [], unbacked)


def _month_row(envelope: dict[str, Any], expected_planned: float) -> MonthRow:
    dados = envelope["dados"]
    anomes = int(dados["anomes"])
    expected = compute_deviation(expected_planned, fixture_sobra(anomes))
    routes = dados.get("rotas") or []
    category = dados.get("categoria_desvio")
    return MonthRow(
        anomes=anomes,
        planned=dados["planejado"],
        realized=dados["realizado"],
        deviation=dados["desvio"],
        status=dados["status"],
        expected_status=expected.status,
        accumulated=dados["acumulado"],
        percent=dados["percentual"],
        category=category["macro"] if isinstance(category, dict) else None,
        routes="; ".join(
            f"{r['id']}: {format_brl(r['aporte_mensal'])} x {r['prazo_meses']}" for r in routes
        )
        or "-",
        local_routes=any(
            WARNING_LOCAL_ROUTE in (r.get("simulacao") or {}).get("avisos", []) for r in routes
        ),
    )


async def main_scenario(report: Report) -> None:
    """Âncora de 202506 a 202512: desvio, rotas, ajuste com consentimento, status e fim."""
    with offline_session() as (fixture_mcp, registry):
        chat = await build_conversation(
            plan_state(ANCHOR_USER_ID, PLAN_START, valor_alvo=TARGET, prazo_meses=TERM)
        )
        planned = INITIAL_CONTRIBUTION
        realized_total = 0.0

        # O modelo tenta outro cliente e outro corte: o escopo vem do state.
        bogus = Call("avancar_mes", {"id_usuario": CONTROL_USER_ID, "ate_anomes": 202512})
        turns = [await chat.say(ADVANCE, bogus, render_tool_answer)]
        report.check(
            "Escopo das chamadas MCP vem do state (modelo pediu controle e 202512)",
            {("âncora", 202507)},
            {(_who(a["id_usuario"]), a["ate_anomes"]) for _, a in fixture_mcp.calls},
        )
        report.answers.append((ADVANCE, turns[-1].text))

        ask = Call(
            "solicitar_consentimento",
            {"acao": "ajustar_plano", "resumo": "Adotar a rota A: manter o prazo."},
        )
        consent = await chat.say("Quero adotar a rota A", ask, render_tool_answer)
        report.check(
            "Consentimento pendente antes do ajuste",
            "pendente",
            consent.state["consentimentos"]["ajustar_plano"]["status"],
        )
        adjust = await chat.say("sim", Call("ajustar_plano", {"rota": "A"}), render_tool_answer)
        report.answers.append(("sim", adjust.text))
        adjusted = _first(adjust).get("dados", {})
        report.check("Ajuste adota a rota A", "A", adjusted.get("rota"))
        report.check(
            "Plano novo vira o plano_id da sessão",
            True,
            adjust.state["plano_id"] == adjusted.get("plano_id") != "plano-inicial",
        )
        planned = adjusted.get("aporte_mensal", planned)

        rows_expected_planned = [INITIAL_CONTRIBUTION]
        for _ in range(5):
            turns.append(await chat.say(ADVANCE, command_router, render_tool_answer))
            rows_expected_planned.append(planned)

        status = await chat.say(STATUS, command_router, render_tool_answer)
        report.answers.append((STATUS, status.text))
        end = await chat.say(ADVANCE, command_router, render_tool_answer)

        for turn, expected_planned in zip(turns, rows_expected_planned, strict=True):
            envelope = _first(turn)
            if "dados" not in envelope:
                report.check("avancar_mes devolve dados", "dados", envelope)
                continue
            row = _month_row(envelope, expected_planned)
            realized_total += max(fixture_sobra(row.anomes), 0.0)
            report.months.append(row)
            report.check(
                f"{row.anomes}: status igual ao desvio.py sobre o fixture",
                row.expected_status,
                row.status,
            )
            report.check(
                f"{row.anomes}: realizado igual ao fixture",
                fixture_sobra(row.anomes),
                row.realized,
            )
            report.check(
                f"{row.anomes}: acumulado igual à soma dos meses positivos",
                money(realized_total),
                row.accumulated,
            )
            report.check(
                f"{row.anomes}: ate_anomes da sessão avançou", row.anomes, turn.state["ate_anomes"]
            )

        report.check(
            "Meses revelados em ordem",
            [202507, 202508, 202509, 202510, 202511, 202512],
            [row.anomes for row in report.months],
        )
        status_data = _first(status).get("dados", {})
        report.check(
            "Status não avança o mês", turns[-1].state["ate_anomes"], status.state["ate_anomes"]
        )
        report.check(
            "Status: acumulado igual ao do último mês",
            report.months[-1].accumulated if report.months else None,
            status_data.get("acumulado"),
        )
        report.check(
            "Depois de 202512: FIM_DO_REPLAY",
            "FIM_DO_REPLAY",
            _first(end).get("erro", {}).get("codigo"),
        )
        report.check("FIM_DO_REPLAY mantém o corte", 202512, end.state["ate_anomes"])
        report.check(
            "Chamadas MCP nunca pedem mês depois do corte",
            [],
            [
                (tool, args)
                for tool, args in fixture_mcp.calls
                if args.get("anomes", 0) > args["ate_anomes"]
            ],
        )

        for turn in [*turns, consent, adjust, status, end]:
            _audit_turn(report, turn)
        report.tool_calls = len(fixture_mcp.calls)
        for event in registry.eventos:
            name = event.tipo_evento.value
            report.events[name] = report.events.get(name, 0) + 1
        report.check(
            "Auditoria: um acompanhamento_mes_avancado por mês",
            6,
            report.events.get("acompanhamento_mes_avancado"),
        )
        report.check("Auditoria: plano_ajustado registrado", 1, report.events.get("plano_ajustado"))
        report.check("Registro: plano ajustado gravado", 1, len(registry.planos))
        report.check(
            "Registro: uma linha de acompanhamento por mês", 6, len(registry.acompanhamentos)
        )


async def edge_cases(report: Report) -> None:
    """Fim do replay, sem plano, cliente de controle e ajuste sem consentimento."""
    cases = [
        ("Corte em 202512", plan_state(ate_anomes=202512), "FIM_DO_REPLAY", 202512),
        ("Sessão sem plano_id", plan_state(plano_id=None), "SEM_PLANO_ATIVO", PLAN_START),
        ("Cliente de controle", plan_state(CONTROL_USER_ID), "DADOS_INSUFICIENTES", PLAN_START),
    ]
    for name, state, code, cut in cases:
        with offline_session():
            chat = await build_conversation(state)
            turn = await chat.say(ADVANCE, command_router, render_tool_answer)
            error = _first(turn).get("erro", {})
            report.check(f"{name}: {code}", code, error.get("codigo"))
            report.check(f"{name}: corte mantido", cut, turn.state["ate_anomes"])
            report.check(
                f"{name}: texto é a mensagem da ferramenta", error.get("mensagem"), turn.text
            )

    for label, governance in (("gate do 005", True), ("guarda local do 006, sem o 005", False)):
        with offline_session(governance=governance):
            chat = await build_conversation(plan_state())
            await chat.say(ADVANCE, command_router, render_tool_answer)
            turn = await chat.say(
                "rota A", Call("ajustar_plano", {"rota": "A"}), render_tool_answer
            )
            report.check(
                f"Ajuste sem consentimento ({label})",
                "CONSENTIMENTO_NECESSARIO",
                _first(turn).get("erro", {}).get("codigo"),
            )
            report.check(
                f"Ajuste sem consentimento ({label}): plano mantido",
                "plano-inicial",
                turn.state["plano_id"],
            )


async def run_eval() -> Report:
    """Roda todos os cenários e devolve o relatório (não grava arquivos)."""
    report = Report()
    await main_scenario(report)
    await edge_cases(report)
    return report


def _pct(value: float) -> str:
    return f"{value:.2f}".replace(".", ",") + "%"


def _brl(value: float) -> str:
    return format_brl(value).replace("R$ ", "R$ ")


def render_result(report: Report) -> str:
    """``resultado.md``: tabelas do roteiro, checagens e respostas."""
    passed = sum(c.ok for c in report.checks)
    lines = [
        "# Eval do acompanhamento (ciclo 006)",
        "",
        "Gerado por `make eval-acompanhamento`. Offline: fixtures de `contracts/fixtures/`,",
        "LLM roteirizado (`ScriptedLlm`), `InMemoryRunner` do ADK, sem rede, GCP ou",
        "modelo real. O agente tem a composição de produção: escopo e verificação",
        "de números do 004, consentimento, guardrails e auditoria do 005.",
        "",
        f"**Resultado: {passed}/{len(report.checks)} verificações ok**"
        f" ({'aprovado' if report.ok else 'reprovado'}).",
        "",
        f"- Chamadas MCP no roteiro principal: {report.tool_calls}.",
        f"- Envelopes de ferramenta conferidos quanto ao corte: {report.envelopes}.",
        f"- Números citados nas respostas e conferidos nos envelopes: {report.cited_numbers}.",
        "",
        "## Roteiro: plano de 60 mil em 24 meses criado em 202506",
        "",
        "Status esperado = `desvio.compute_deviation(planejado, sobra do fixture)`,",
        "calculado pelo eval sem passar pela ferramenta. Tolerância de 10% do planejado.",
        "",
        "| Mês | Planejado | Realizado | Desvio | Status | Esperado | Acumulado | % meta |"
        " Categoria | Rotas |",
        "|---|---:|---:|---:|---|---|---:|---:|---|---|",
    ]
    for row in report.months:
        mark = "ok" if row.status == row.expected_status else "DIVERGE"
        routes = row.routes + (" (estimativa local)" if row.local_routes else "")
        lines.append(
            f"| {row.anomes} | {_brl(row.planned)} | {_brl(row.realized)} |"
            f" {_brl(row.deviation)} | {row.status} | {row.expected_status} ({mark}) |"
            f" {_brl(row.accumulated)} | {_pct(row.percent)} | {row.category or '-'} | {routes} |"
        )
    lines += [
        "",
        "Em 202507 o cliente adota a rota A com consentimento; de 202508 em diante o",
        "planejado é o aporte da rota A.",
        "",
        "## Auditoria (registro em memória, compartilhado por 005 e 006)",
        "",
        "| Evento | Quantidade |",
        "|---|---:|",
        *[f"| `{name}` | {count} |" for name, count in sorted(report.events.items())],
        "",
        "## Verificações",
        "",
        "| Verificação | Esperado | Obtido | Ok |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        expected = check.expected.replace("|", "\\|")
        obtained = check.obtained.replace("|", "\\|")
        lines.append(
            f"| {check.name} | {expected} | {obtained} | {'sim' if check.ok else '**não**'} |"
        )
    lines += ["", "## Respostas ao cliente (LLM roteirizado, números das ferramentas)", ""]
    for said, answer in report.answers:
        lines += [f"**Cliente:** {said}", "", *[f"> {line}" for line in answer.splitlines()], ""]
    lines += [
        "## Limitações",
        "",
        "- O LLM é roteirizado: o eval mede ferramentas, estado, corte temporal e",
        "  auditoria, não a redação do Gemini.",
        "- O `simular_objetivo` do mock devolve sempre o golden do corte. Quando a",
        "  resposta não corresponde ao pedido, a rota usa a estimativa local de",
        "  `routes.py` e avisa. Reavaliar com o 003 (resposta calculada pelo MCP real).",
        "- Os números dependem dos fixtures do 001. Se `make fixtures` mudar os",
        "  valores, rode de novo e revise esta página.",
        "",
    ]
    return "\n".join(lines)


def render_summary(report: Report) -> str:
    """``RESULTADOS.md``: resumo curto que aponta para ``resultado.md``."""
    passed = sum(c.ok for c in report.checks)
    months = ", ".join(f"{r.anomes} {r.status}" for r in report.months)
    return "\n".join(
        [
            "# Resultados do eval do acompanhamento (006)",
            "",
            f"- Situação: **{'aprovado' if report.ok else 'reprovado'}**"
            f" ({passed}/{len(report.checks)} verificações).",
            f"- Meses revelados: {months}.",
            "- Corte temporal: nenhum envelope com período depois do `ate_anomes`.",
            "- Detalhes, tabelas e respostas: [resultado.md](resultado.md).",
            "- Como rodar: `make eval-acompanhamento` (offline).",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path, default=EVAL_DIR, help="diretório dos .md")
    args = parser.parse_args(argv)
    os.environ.setdefault("BUSSOLA_FAKES", "TRUE")
    configurar_logging(nivel="WARNING")
    logging.getLogger("google_adk").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning)
    report = asyncio.run(run_eval())
    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / "resultado.md").write_text(render_result(report), encoding="utf-8")
    (args.saida / "RESULTADOS.md").write_text(render_summary(report), encoding="utf-8")
    passed = sum(c.ok for c in report.checks)
    print(f"eval acompanhamento: {passed}/{len(report.checks)} ok -> {args.saida / 'resultado.md'}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
