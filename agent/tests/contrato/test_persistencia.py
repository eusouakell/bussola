"""Linhas de ``bussola_app`` e registro em memória (contratos §6; AC-10)."""

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from bussola_agent.persistencia import (
    Acompanhamento,
    Consentimento,
    EventoAuditoria,
    Plano,
    RegistroApp,
    RegistroEmMemoria,
    TipoEvento,
)

ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"


def _plano(**kwargs) -> Plano:
    dados = {
        "session_id": "s1",
        "id_usuario": ANCORA,
        "objetivo": "Reserva de emergência",
        "valor_alvo": 10000.0,
        "prazo_meses": 12,
        "cenario": "equilibrado",
        "aporte_mensal": 833.33,
        "ate_anomes": 202506,
    }
    dados.update(kwargs)
    return Plano(**dados)


def _eh_uuid4(valor: str) -> bool:
    return uuid.UUID(valor).version == 4


def test_tipo_evento_tem_os_12_valores() -> None:
    assert [t.value for t in TipoEvento] == [
        "sessao_iniciada",
        "estado_alterado",
        "ferramenta_chamada",
        "consentimento_solicitado",
        "consentimento_decidido",
        "plano_criado",
        "acao_executada",
        "guardrail_bloqueio",
        "acompanhamento_mes_avancado",
        "desvio_detectado",
        "rota_recalculada",
        "plano_ajustado",
    ]


def test_registro_em_memoria_cumpre_a_interface() -> None:
    assert isinstance(RegistroEmMemoria(), RegistroApp)
    assert not isinstance(object(), RegistroApp)


def test_padroes_de_id_e_timestamp() -> None:
    antes = datetime.now(UTC)
    plano = _plano()
    consentimento = Consentimento(
        session_id="s1", acao="criar_plano", decisao="aceito", texto_apresentado="Posso criar?"
    )
    evento = EventoAuditoria(session_id="s1", estado="AGIR", tipo_evento="plano_criado")
    acompanhamento = Acompanhamento(
        plano_id=plano.plano_id, anomes=202507, planejado=800, realizado=700, desvio=-100
    )
    assert _eh_uuid4(plano.plano_id)
    assert _eh_uuid4(consentimento.consent_id)
    assert _eh_uuid4(evento.evento_id)
    assert _plano().plano_id != plano.plano_id
    for instante in (plano.criado_em, consentimento.ts, evento.ts, acompanhamento.ts):
        assert instante.tzinfo is not None and instante.utcoffset() == timedelta(0)
        assert instante >= antes
    assert consentimento.plano_id is None
    assert evento.ferramenta is None and evento.resumo == {}
    assert acompanhamento.categoria_desvio is None and acompanhamento.acao_sugerida is None


def test_round_trip_no_registro() -> None:
    """AC-10: grava planos, consentimentos, eventos e acompanhamentos e lê o plano."""
    registro = RegistroEmMemoria()
    plano = _plano()
    assert registro.registrar_plano(plano) == plano.plano_id
    consentimento = Consentimento(
        session_id="s1",
        plano_id=plano.plano_id,
        acao="criar_plano",
        decisao="recusado",
        texto_apresentado="Posso criar o plano?",
    )
    assert registro.registrar_consentimento(consentimento) == consentimento.consent_id
    evento = EventoAuditoria(
        session_id="s1",
        estado="AGIR",
        tipo_evento=TipoEvento.CONSENTIMENTO_DECIDIDO,
        ferramenta="criar_plano",
        resumo={"decisao": "recusado"},
    )
    assert registro.registrar_evento(evento) == evento.evento_id
    acompanhamento = Acompanhamento(
        plano_id=plano.plano_id,
        anomes=202507,
        planejado=833.33,
        realizado=600.0,
        desvio=-233.33,
        categoria_desvio="Restaurantes",
        acao_sugerida="Reduzir comer fora.",
    )
    assert registro.registrar_acompanhamento(acompanhamento) is None

    assert registro.obter_plano(plano.plano_id) == plano
    assert registro.obter_plano(str(uuid.uuid4())) is None
    assert registro.planos == [plano]
    assert registro.consentimentos == [consentimento]
    assert registro.eventos == [evento]
    assert registro.acompanhamentos == [acompanhamento]


def test_registro_guarda_copias() -> None:
    registro = RegistroEmMemoria()
    plano = _plano()
    registro.registrar_plano(plano)
    plano.objetivo = "alterado depois"
    lido = registro.obter_plano(plano.plano_id)
    assert lido is not None and lido.objetivo == "Reserva de emergência"
    lido.objetivo = "alterado na cópia"
    assert registro.obter_plano(plano.plano_id).objetivo == "Reserva de emergência"


def test_obter_plano_devolve_a_versao_mais_recente() -> None:
    registro = RegistroEmMemoria()
    plano = _plano()
    registro.registrar_plano(plano)
    ajustado = plano.model_copy(update={"aporte_mensal": 900.0, "prazo_meses": 11})
    registro.registrar_plano(ajustado)
    assert registro.obter_plano(plano.plano_id).aporte_mensal == 900.0


def test_registro_rejeita_tipo_errado() -> None:
    registro = RegistroEmMemoria()
    with pytest.raises(TypeError):
        registro.registrar_plano({"plano_id": "x"})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        registro.registrar_evento(_plano())  # type: ignore[arg-type]


def test_serializacao_para_linha_json() -> None:
    evento = EventoAuditoria(
        session_id="s1", estado="ENTENDER", tipo_evento="ferramenta_chamada", resumo={"n": 1}
    )
    linha = evento.model_dump(mode="json")
    assert linha["estado"] == "ENTENDER"
    assert linha["tipo_evento"] == "ferramenta_chamada"
    assert linha["resumo"] == {"n": 1}
    assert isinstance(linha["ts"], str)


def test_timestamp_sem_fuso_vira_utc() -> None:
    plano = _plano(criado_em=datetime(2025, 6, 1, 12, 0))
    assert plano.criado_em == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    brasilia = timezone(timedelta(hours=-3))
    plano = _plano(criado_em=datetime(2025, 6, 1, 9, 0, tzinfo=brasilia))
    assert plano.criado_em == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    assert plano.criado_em.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"id_usuario": "nao-uuid-secreto"},
        {"ate_anomes": 202601},
        {"valor_alvo": 0},
        {"prazo_meses": 0},
        {"aporte_mensal": -1},
        {"campo_extra": 1},
    ],
)
def test_plano_invalido_sem_eco(kwargs: dict) -> None:
    with pytest.raises(ValidationError) as erro:
        _plano(**kwargs)
    assert "nao-uuid-secreto" not in str(erro.value)


def test_validacoes_de_enum_e_literal() -> None:
    with pytest.raises(ValidationError):
        Consentimento(session_id="s", acao="a", decisao="talvez", texto_apresentado="t")
    with pytest.raises(ValidationError):
        EventoAuditoria(session_id="s", estado="AGIR", tipo_evento="evento_inventado")
    with pytest.raises(ValidationError):
        EventoAuditoria(session_id="s", estado="PASSEAR", tipo_evento="plano_criado")
    with pytest.raises(ValidationError):
        EventoAuditoria(
            session_id="s", estado="AGIR", tipo_evento="plano_criado", resumo={"x": object()}
        )
    with pytest.raises(ValidationError):
        Acompanhamento(plano_id="p", anomes=202413, planejado=1, realizado=1, desvio=0)
