"""Linhas do dataset ``bussola_app`` e o registro da aplicação (contratos §6).

Código de contrato (constituição X): mudanças só via PR ``contracts: <mudança>``.

Os modelos espelham ``contracts/bigquery/bussola_app.sql`` (nome, tipo e
nulidade de cada coluna; conferido pelo teste de contrato AC-03).

- :class:`RegistroApp` é a interface; :class:`RegistroEmMemoria` é o fake.
- O ``RegistroBigQuery`` (005, ``persistencia_bq.py``) grava via streaming
  insert em ``BQ_DATASET_APP``. Para gerar a linha, use
  ``modelo.model_dump(mode="json")``.
"""

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Protocol, runtime_checkable

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from bussola_agent.estado import EstadoJornada, anomes_valido, id_usuario_valido


class TipoEvento(StrEnum):
    """``tipo_evento`` da tabela ``auditoria`` (contratos §6)."""

    SESSAO_INICIADA = "sessao_iniciada"
    ESTADO_ALTERADO = "estado_alterado"
    FERRAMENTA_CHAMADA = "ferramenta_chamada"
    CONSENTIMENTO_SOLICITADO = "consentimento_solicitado"
    CONSENTIMENTO_DECIDIDO = "consentimento_decidido"
    PLANO_CRIADO = "plano_criado"
    ACAO_EXECUTADA = "acao_executada"
    GUARDRAIL_BLOQUEIO = "guardrail_bloqueio"
    ACOMPANHAMENTO_MES_AVANCADO = "acompanhamento_mes_avancado"
    DESVIO_DETECTADO = "desvio_detectado"
    ROTA_RECALCULADA = "rota_recalculada"
    PLANO_AJUSTADO = "plano_ajustado"


def _novo_id() -> str:
    return str(uuid.uuid4())


def _agora() -> datetime:
    return datetime.now(UTC)


def _em_utc(valor: datetime) -> datetime:
    """Datas sem fuso são tratadas como UTC; com fuso, convertidas para UTC."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC)


def _validar_id_usuario(valor: str) -> str:
    if not id_usuario_valido(valor):
        raise ValueError("id_usuario deve ser um UUID v4.")
    return valor.lower()


def _validar_anomes(valor: int) -> int:
    if not anomes_valido(valor):
        raise ValueError("anomes deve estar entre 202501 e 202512.")
    return valor


IdUsuario = Annotated[str, AfterValidator(_validar_id_usuario)]
Anomes = Annotated[int, AfterValidator(_validar_anomes)]
TimestampUtc = Annotated[datetime, AfterValidator(_em_utc)]


class _Linha(BaseModel):
    # ``hide_input_in_errors``: erros de validação não ecoam o valor recebido.
    model_config = ConfigDict(extra="forbid", validate_assignment=True, hide_input_in_errors=True)


class Plano(_Linha):
    """Linha de ``bussola_app.planos``."""

    plano_id: str = Field(default_factory=_novo_id)
    session_id: str
    id_usuario: IdUsuario
    objetivo: str
    valor_alvo: float = Field(gt=0)
    prazo_meses: int = Field(ge=1, le=360)
    cenario: str
    aporte_mensal: float = Field(ge=0)
    ate_anomes: Anomes
    criado_em: TimestampUtc = Field(default_factory=_agora)


class Consentimento(_Linha):
    """Linha de ``bussola_app.consentimentos``."""

    consent_id: str = Field(default_factory=_novo_id)
    session_id: str
    plano_id: str | None = None
    acao: str
    decisao: Literal["aceito", "recusado"]
    texto_apresentado: str
    ts: TimestampUtc = Field(default_factory=_agora)


class EventoAuditoria(_Linha):
    """Linha de ``bussola_app.auditoria``.

    ``resumo`` precisa ser serializável em JSON e não deve trazer prompt,
    texto de lançamentos, chaves ou tokens.
    """

    evento_id: str = Field(default_factory=_novo_id)
    session_id: str
    estado: EstadoJornada
    tipo_evento: TipoEvento
    ferramenta: str | None = None
    resumo: dict[str, Any] = Field(default_factory=dict)
    ts: TimestampUtc = Field(default_factory=_agora)

    @field_validator("resumo")
    @classmethod
    def _resumo_json(cls, valor: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(valor)
        except (TypeError, ValueError):
            raise ValueError("resumo deve ser serializável em JSON.") from None
        return valor


class Acompanhamento(_Linha):
    """Linha de ``bussola_app.acompanhamento``."""

    plano_id: str
    anomes: Anomes
    planejado: float
    realizado: float
    desvio: float
    categoria_desvio: str | None = None
    acao_sugerida: str | None = None
    ts: TimestampUtc = Field(default_factory=_agora)


# Modelo de cada tabela de ``bussola_app`` (acréscimo do 000, usado no teste AC-03).
TABELAS: dict[str, type[BaseModel]] = {
    "planos": Plano,
    "consentimentos": Consentimento,
    "auditoria": EventoAuditoria,
    "acompanhamento": Acompanhamento,
}


@runtime_checkable
class RegistroApp(Protocol):
    def registrar_plano(self, plano: Plano) -> str: ...
    def registrar_consentimento(self, c: Consentimento) -> str: ...
    def registrar_evento(self, e: EventoAuditoria) -> str: ...
    def registrar_acompanhamento(self, a: Acompanhamento) -> None: ...
    def obter_plano(self, plano_id: str) -> Plano | None: ...


def _exigir(valor: object, tipo: type[BaseModel]) -> None:
    if not isinstance(valor, tipo):
        raise TypeError(f"Esperado um {tipo.__name__}.")


class RegistroEmMemoria:
    """Fake de :class:`RegistroApp` que guarda cópias das linhas em listas."""

    def __init__(self) -> None:
        self.planos: list[Plano] = []
        self.consentimentos: list[Consentimento] = []
        self.eventos: list[EventoAuditoria] = []
        self.acompanhamentos: list[Acompanhamento] = []

    def registrar_plano(self, plano: Plano) -> str:
        _exigir(plano, Plano)
        self.planos.append(plano.model_copy(deep=True))
        return plano.plano_id

    def registrar_consentimento(self, c: Consentimento) -> str:
        _exigir(c, Consentimento)
        self.consentimentos.append(c.model_copy(deep=True))
        return c.consent_id

    def registrar_evento(self, e: EventoAuditoria) -> str:
        _exigir(e, EventoAuditoria)
        self.eventos.append(e.model_copy(deep=True))
        return e.evento_id

    def registrar_acompanhamento(self, a: Acompanhamento) -> None:
        _exigir(a, Acompanhamento)
        self.acompanhamentos.append(a.model_copy(deep=True))

    def obter_plano(self, plano_id: str) -> Plano | None:
        """Cópia da versão mais recente do plano com ``plano_id``, ou ``None``."""
        for plano in reversed(self.planos):
            if plano.plano_id == plano_id:
                return plano.model_copy(deep=True)
        return None
