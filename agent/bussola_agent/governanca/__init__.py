"""Cycle 005: consent, governance and audit (contratos §6).

Importing this package registers, through the extension points only:

- tools: ``solicitar_consentimento`` (free) and the sensitive simulated
  actions ``criar_plano``, ``ativar_lembretes``, ``simular_contratacao`` and
  ``compartilhar_dados`` (always refused);
- prompt fragments 50, 55 and 60;
- callbacks:

  - ``before_model`` 10: session start audit, safety settings and input
    guardrail;
  - ``before_model`` 20: consent reply reader;
  - ``before_tool`` 20: consent gate;
  - ``before_tool`` 90 / ``after_tool`` 90: tool call audit;
  - ``after_model`` 10: output guardrail and consent chips.

Importing does not touch the network: the registry, the clock and the
guardrail screener are built lazily by :mod:`.services`.
"""

from bussola_agent import callbacks, extensoes
from bussola_agent.governanca import acoes, audit, consent, guardrails, instructions

ORDER_INPUT_GUARDRAIL = 10
ORDER_CONSENT_READER = 20
ORDER_GATE = 20
ORDER_AUDIT = 90
ORDER_OUTPUT_GUARDRAIL = 10

SENSITIVE_TOOLS = (
    acoes.criar_plano,
    acoes.ativar_lembretes,
    acoes.simular_contratacao,
    acoes.compartilhar_dados,
)


def register() -> None:
    """Registers tools, instructions and callbacks of cycle 005.

    Idempotent: a second call (the package imported again after the tests
    unload it) changes nothing.
    """
    if consent.solicitar_consentimento not in extensoes.ferramentas():
        _register_extensions()
    if consent.gate not in callbacks.registrados("before_tool"):
        _register_callbacks()


def _register_extensions() -> None:
    extensoes.registrar_ferramenta(consent.solicitar_consentimento)
    for tool in SENSITIVE_TOOLS:
        extensoes.registrar_ferramenta(tool, sensivel=True)
    extensoes.registrar_instrucao(instructions.ORDER_CONSENT, instructions.CONSENT_POLICY)
    extensoes.registrar_instrucao(instructions.ORDER_ACTIONS, instructions.ACTIONS_POLICY)
    extensoes.registrar_instrucao(instructions.ORDER_LIMITS, instructions.limits_policy())


def _register_callbacks() -> None:
    callbacks.registrar("before_model", audit.record_session_start, ORDER_INPUT_GUARDRAIL)
    callbacks.registrar("before_model", guardrails.screen_input, ORDER_INPUT_GUARDRAIL)
    callbacks.registrar("before_model", consent.read_reply, ORDER_CONSENT_READER)
    callbacks.registrar("before_tool", consent.gate, ORDER_GATE)
    callbacks.registrar("before_tool", audit.remember_tool_call, ORDER_AUDIT)
    callbacks.registrar("after_tool", audit.record_tool_call, ORDER_AUDIT)
    callbacks.registrar("after_model", guardrails.screen_output, ORDER_OUTPUT_GUARDRAIL)


register()
