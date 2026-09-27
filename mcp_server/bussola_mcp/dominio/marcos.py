"""Engine de marcos financeiros intermediários (ciclo 009).

Funções **puras**, sem I/O e sem estado: mesma entrada, mesma saída
(specs/009-marcos-financeiros FR-018). Regra de negócio fica aqui; a
ferramenta só valida a entrada, lê o repositório e monta o envelope.

O que a engine faz, na ordem:

1. :func:`contexto_de_perfil` transforma as linhas de ``perfil_mensal`` e
   ``parcelas`` num :class:`~bussola_mcp.contratos.ContextoFinanceiro`;
2. :func:`diagnosticar` diz **por que** o objetivo não cabe, com um código por
   gatilho (FR-001);
3. :func:`planejar` monta a trajetória de marcos, ordenada pelos quatro níveis
   de prioridade, com um único próximo marco destacado (FR-008, FR-009);
4. :func:`avisos_do_plano` devolve os avisos determinísticos do envelope.

Premissas em :class:`~bussola_mcp.contratos.RegrasMarco`, decididas em
``specs/009-marcos-financeiros/questoes.md`` (Q-009-1 a Q-009-4). Nada de
rendimento assumido, nada de aumento de renda suposto: o que não existe na base
vira aviso, nunca número (FR-004).

A aritmética vem de ``dominio/simulacao.py`` (ciclo 001, já em ``main``):
:func:`meses_para` delega em ``months_to_reach``, as médias em ``mean_brl`` e
``median_brl`` e o texto de prazo em ``format_months``. O que fica aqui é o que
a engine de marcos tem de diferente: rendimento zero (a mesma premissa de
``RegrasCenario``), "sem aporte possível" como ``None`` em vez de erro, série
vazia como ``0.0`` e :func:`_texto_brl`, que escreve o valor **com** centavos
(``simulacao.format_brl_whole`` escreve sem, e os dois não são
intercambiáveis). Dívida T032 do ciclo 009 quitada.
"""

from bussola_mcp.contratos import (
    AVISO_MARCO_NAO_GARANTE,
    AVISO_SALDO_COMO_RECURSO,
    AVISO_SALDO_NEGATIVO,
    AVISO_SEM_PATRIMONIO,
    AVISO_SEM_RENDA,
    AVISO_SEM_RENDIMENTO,
    NIVEL_TIPO_MARCO,
    CodigoMotivo,
    ContextoFinanceiro,
    DadosPlanejarMarcos,
    Marco,
    Motivo,
    ObjetivoMarco,
    Parcela,
    PerfilMes,
    RegrasMarco,
    TipoMarco,
    brl,
)
from bussola_mcp.dominio.simulacao import format_months, mean_brl, median_brl, months_to_reach

RESSALVA_NAO_GARANTE = (
    "Este marco melhora sua posição financeira e mantém o objetivo aberto, "
    "mas atingi-lo não garante o objetivo final."
)
RESSALVA_DECISAO_E_SUA = (
    "A decisão de mudar valor, prazo ou prioridade do objetivo é sua: nada aqui "
    "troca o seu objetivo automaticamente."
)
RESSALVA_SEM_TRAJETORIA = (
    "Hoje não há uma trajetória financeiramente responsável para projetar esse "
    "objetivo com segurança nas condições atuais. Podemos, porém, trabalhar num "
    "primeiro marco concreto que aumente suas possibilidades futuras."
)


# ---------------------------------------------------------------------------
# Aritmética (rendimento zero; ver docstring do módulo)
# ---------------------------------------------------------------------------


def meses_para(falta: float, aporte: float) -> int | None:
    """Meses inteiros para juntar ``falta`` guardando ``aporte`` por mês.

    ``0`` quando não falta nada; ``None`` quando não há aporte possível — é a
    única diferença em relação a ``simulacao.months_to_reach``, que trata aporte
    não positivo como erro de entrada.
    """
    if falta <= 0:
        return 0
    if aporte <= 0:
        return None
    return months_to_reach(falta, aporte)


def aporte_para(falta: float, prazo_meses: int) -> float:
    """Aporte mensal para juntar ``falta`` em ``prazo_meses``, em BRL.

    Não é ``simulacao.aporte_para_prazo``: aqui a entrada é o que **falta**
    (``0`` é um valor legítimo, não erro) e a saída é só o número, sem
    viabilidade nem motivo.
    """
    if prazo_meses <= 0:
        return 0.0
    return brl(max(falta, 0.0) / prazo_meses)


def _media(valores: list[float]) -> float:
    """``simulacao.mean_brl`` com série vazia valendo ``0.0`` em vez de erro."""
    return mean_brl(valores) if valores else 0.0


def _mediana(valores: list[float]) -> float:
    """``simulacao.median_brl`` com série vazia valendo ``0.0`` em vez de erro."""
    return median_brl(valores) if valores else 0.0


def _texto_brl(valor: float) -> str:
    """``13843.56`` -> ``"R$ 13.843,56"`` (frase determinística, não é formatação de UI).

    Com centavos, ao contrário de ``simulacao.format_brl_whole``: os textos de
    marco citam o valor exato do objetivo, e arredondar mudaria o número que o
    cliente lê.
    """
    inteiro, _, centavos = f"{brl(valor):,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


# ---------------------------------------------------------------------------
# Contexto financeiro
# ---------------------------------------------------------------------------


def _parcelas_ativas(parcelas: list[Parcela]) -> list[Parcela]:
    """Parcelas do último mês disponível que ainda não terminaram."""
    if not parcelas:
        return []
    ultimo = max(p.anomes for p in parcelas)
    return [p for p in parcelas if p.anomes == ultimo and p.parcela_atual <= p.parcela_total]


def contexto_de_perfil(
    perfil: list[PerfilMes], parcelas: list[Parcela], regras: RegrasMarco
) -> ContextoFinanceiro:
    """Retrato determinístico do cliente a partir das linhas já filtradas pelo corte.

    ``perfil`` vem de ``RepositorioFinanceiro.perfil_mensal`` (ordenado por
    ``anomes``) e ``parcelas`` de ``RepositorioFinanceiro.parcelas``.
    """
    meses = sorted(perfil, key=lambda linha: linha.anomes)
    renda_media = _media([linha.renda for linha in meses])
    gasto_medio = _media([linha.gasto for linha in meses])
    saldo_atual = brl(meses[-1].saldo_final) if meses else 0.0
    recursos = brl(max(saldo_atual, 0.0)) if regras.usar_saldo_atual else 0.0

    ativas = _parcelas_ativas(parcelas)
    parcelas_mensais = brl(sum(p.vlr for p in ativas))
    restantes = [max(p.parcela_total - p.parcela_atual, 0) for p in ativas]

    ausentes = ["PATRIMONIO", "INVESTIMENTOS"]
    if not regras.usar_saldo_atual:
        ausentes.append("RESERVA")

    return ContextoFinanceiro(
        renda_media=renda_media,
        gasto_medio=gasto_medio,
        sobra_media=_media([linha.sobra for linha in meses]),
        sobra_mediana=_mediana([linha.sobra for linha in meses]),
        meses_negativos=sum(1 for linha in meses if linha.sobra < 0),
        meses_considerados=len(meses),
        saldo_atual=saldo_atual,
        recursos_disponiveis=recursos,
        juros_pagos_media=_media([linha.juros for linha in meses]),
        parcelas_mensais=parcelas_mensais,
        comprometimento_renda_pct=(
            brl(parcelas_mensais / renda_media * 100) if renda_media > 0 else 0.0
        ),
        meses_ate_fim_parcela=min(restantes) if restantes else None,
        dados_ausentes=ausentes,
    )


def capacidade_sustentavel(contexto: ContextoFinanceiro, regras: RegrasMarco) -> float:
    """Aporte mensal que cabe na sobra mediana, pela fração das regras."""
    return brl(regras.pct_capacidade_sustentavel * max(contexto.sobra_mediana, 0.0))


def _falta(valor_alvo: float, contexto: ContextoFinanceiro) -> float:
    return brl(max(valor_alvo - contexto.recursos_disponiveis, 0.0))


# ---------------------------------------------------------------------------
# Diagnóstico (FR-001)
# ---------------------------------------------------------------------------


def diagnosticar(
    valor_alvo: float, prazo_meses: int, contexto: ContextoFinanceiro, regras: RegrasMarco
) -> list[Motivo]:
    """Motivos pelos quais o objetivo não cabe nas condições atuais.

    Lista vazia = o objetivo cabe e não há problema estrutural: nenhum marco é
    proposto (FR-002).
    """
    capacidade = capacidade_sustentavel(contexto, regras)
    aporte_necessario = aporte_para(_falta(valor_alvo, contexto), prazo_meses)
    alvo_reserva = brl(regras.meses_reserva * contexto.gasto_medio)
    limite_juros = brl(regras.pct_juros_renda_divida_cara * contexto.renda_media)
    limite_aporte_renda = brl(regras.pct_aporte_renda_max * contexto.renda_media)
    limite_recursos = brl(regras.pct_recursos_minimo_meta * valor_alvo)
    fracao_negativos = (
        contexto.meses_negativos / contexto.meses_considerados
        if contexto.meses_considerados
        else 0.0
    )

    motivos: list[Motivo] = []

    if contexto.sobra_mediana <= 0:
        motivos.append(
            Motivo(
                codigo=CodigoMotivo.CAPACIDADE_INSUFICIENTE,
                observado=contexto.sobra_mediana,
                limite=0.0,
                explicacao=(
                    "Sua sobra mensal mediana no período é de "
                    f"{_texto_brl(contexto.sobra_mediana)}, então hoje não há valor "
                    "recorrente disponível para guardar."
                ),
            )
        )

    if fracao_negativos > regras.pct_meses_negativos_max or contexto.saldo_atual < 0:
        detalhe = (
            f"o saldo atual está em {_texto_brl(contexto.saldo_atual)}"
            if contexto.saldo_atual < 0
            else (
                f"a sobra ficou negativa em {contexto.meses_negativos} de "
                f"{contexto.meses_considerados} meses"
            )
        )
        motivos.append(
            Motivo(
                codigo=CodigoMotivo.RISCO_EXCESSIVO,
                observado=brl(fracao_negativos),
                limite=brl(regras.pct_meses_negativos_max),
                explicacao=(
                    f"Seu fluxo de caixa ainda oscila: {detalhe}. Guardar para o objetivo "
                    "nessas condições aumentaria o risco de precisar do dinheiro no meio "
                    "do caminho."
                ),
            )
        )

    juros_caros = contexto.renda_media > 0 and contexto.juros_pagos_media >= limite_juros
    parcelas_pesadas = contexto.comprometimento_renda_pct > regras.pct_comprometimento_renda_max
    if juros_caros or parcelas_pesadas:
        if parcelas_pesadas:
            observado, limite = (
                contexto.comprometimento_renda_pct,
                regras.pct_comprometimento_renda_max,
            )
            explicacao = (
                f"Suas parcelas somam {_texto_brl(contexto.parcelas_mensais)} por mês e "
                f"comprometem {contexto.comprometimento_renda_pct:.1f}% da sua renda, acima do "
                f"limite de {regras.pct_comprometimento_renda_max:.0f}% que usamos como referência."
            )
        else:
            observado, limite = contexto.juros_pagos_media, limite_juros
            explicacao = (
                f"Você paga em média {_texto_brl(contexto.juros_pagos_media)} de juros por mês. "
                "Cada real de juros evitado rende mais do que qualquer aplicação segura, "
                "então ele vem antes do objetivo."
            )
        motivos.append(
            Motivo(
                codigo=CodigoMotivo.DIVIDA_A_RESOLVER,
                observado=observado,
                limite=limite,
                explicacao=explicacao,
            )
        )

    if contexto.gasto_medio > 0 and contexto.recursos_disponiveis < alvo_reserva:
        motivos.append(
            Motivo(
                codigo=CodigoMotivo.SEM_RESERVA,
                observado=contexto.recursos_disponiveis,
                limite=alvo_reserva,
                explicacao=(
                    f"Sua reserva de emergência de referência é de {_texto_brl(alvo_reserva)} "
                    f"({regras.meses_reserva} meses de gasto médio) e você tem hoje "
                    f"{_texto_brl(contexto.recursos_disponiveis)} disponíveis."
                ),
            )
        )

    if contexto.recursos_disponiveis < limite_recursos:
        motivos.append(
            Motivo(
                codigo=CodigoMotivo.VALOR_DISTANTE_DOS_RECURSOS,
                observado=contexto.recursos_disponiveis,
                limite=limite_recursos,
                explicacao=(
                    f"O objetivo é de {_texto_brl(valor_alvo)} e os recursos que você já tem "
                    f"somam {_texto_brl(contexto.recursos_disponiveis)}: o ponto de partida "
                    "ainda está distante da meta."
                ),
            )
        )

    if contexto.renda_media > 0 and aporte_necessario > limite_aporte_renda:
        motivos.append(
            Motivo(
                codigo=CodigoMotivo.RENDA_NAO_SUSTENTA,
                observado=aporte_necessario,
                limite=limite_aporte_renda,
                explicacao=(
                    f"Fechar o objetivo no prazo pedido exigiria guardar "
                    f"{_texto_brl(aporte_necessario)} por mês, acima dos "
                    f"{regras.pct_aporte_renda_max:.0%} da sua renda média que tratamos como "
                    "teto seguro."
                ),
            )
        )

    if aporte_necessario > max(contexto.sobra_mediana, 0.0):
        motivos.append(
            Motivo(
                codigo=CodigoMotivo.PREMISSA_IRREALISTA,
                observado=aporte_necessario,
                limite=brl(max(contexto.sobra_mediana, 0.0)),
                explicacao=(
                    f"O aporte necessário de {_texto_brl(aporte_necessario)} por mês passa de "
                    f"toda a sua sobra mediana ({_texto_brl(max(contexto.sobra_mediana, 0.0))}). "
                    "Só fecharia com premissas que não usamos, como valorização de investimento."
                ),
            )
        )

    if aporte_necessario > capacidade:
        motivos.append(
            Motivo(
                codigo=CodigoMotivo.PRAZO_NAO_CABE,
                observado=aporte_necessario,
                limite=capacidade,
                explicacao=(
                    f"Em {format_months(prazo_meses)}, o objetivo pede "
                    f"{_texto_brl(aporte_necessario)} por mês, e a sua capacidade sustentável "
                    f"hoje é de {_texto_brl(capacidade)} por mês."
                ),
            )
        )

    return motivos


# ---------------------------------------------------------------------------
# Marcos por nível de prioridade (FR-008)
# ---------------------------------------------------------------------------


def _marco(
    tipo: TipoMarco,
    titulo: str,
    indicador: str,
    por_que: str,
    relacao: str,
    valor_alvo: float | None = None,
    prazo_meses: int | None = None,
    aporte_mensal: float | None = None,
) -> dict[str, object]:
    """Marco sem ``ordem`` (atribuída na montagem da trajetória)."""
    return {
        "nivel": NIVEL_TIPO_MARCO[tipo],
        "tipo": tipo,
        "titulo": titulo,
        "indicador": indicador,
        "valor_alvo": valor_alvo,
        "prazo_meses": prazo_meses,
        "aporte_mensal": aporte_mensal,
        "por_que": por_que,
        "relacao_com_objetivo": relacao,
    }


def _marco_equilibrar_fluxo(contexto: ContextoFinanceiro, regras: RegrasMarco) -> dict[str, object]:
    falta_mensal = brl(
        max(abs(min(contexto.sobra_mediana, 0.0)), abs(min(contexto.saldo_atual, 0.0)))
    )
    return _marco(
        TipoMarco.EQUILIBRAR_FLUXO,
        titulo="Equilibrar o fluxo de caixa do mês",
        indicador=(
            "sobra mensal maior ou igual a zero em "
            f"{format_months(regras.meses_fluxo_equilibrado)} "
            "seguidos, com saldo fora do negativo"
        ),
        por_que=(
            "Com o mês fechando no positivo, qualquer valor guardado deixa de ser desfeito no mês "
            "seguinte, e você para de pagar pelo descompasso."
        ),
        relacao=(
            "É o primeiro degrau do objetivo: sem sobra estável não existe aporte que se sustente "
            "até lá."
        ),
        valor_alvo=falta_mensal or None,
        prazo_meses=regras.meses_fluxo_equilibrado,
    )


def _marco_reduzir_divida(contexto: ContextoFinanceiro, regras: RegrasMarco) -> dict[str, object]:
    teto_parcelas = brl(regras.pct_comprometimento_renda_max / 100 * contexto.renda_media)
    a_liberar = brl(max(contexto.parcelas_mensais - teto_parcelas, contexto.juros_pagos_media, 0.0))
    return _marco(
        TipoMarco.REDUZIR_DIVIDA_CARA,
        titulo="Reduzir o custo das dívidas atuais",
        indicador=(
            f"juros mensais abaixo de {regras.pct_juros_renda_divida_cara:.0%} da renda e parcelas "
            f"abaixo de {regras.pct_comprometimento_renda_max:.0f}% da renda"
        ),
        por_que=(
            f"Liberar {_texto_brl(a_liberar)} por mês hoje comprometidos com dívida e juros é "
            "ganho imediato e certo, sem depender de nenhuma premissa de mercado."
        ),
        relacao=(
            "Cada real que sai dos juros passa a estar disponível para o objetivo, aumentando a "
            "sua capacidade de aporte antes de começar a acumular."
        ),
        valor_alvo=a_liberar or None,
        prazo_meses=contexto.meses_ate_fim_parcela or None,
    )


def _marcos_reserva(
    contexto: ContextoFinanceiro, regras: RegrasMarco, prazo_objetivo: int, capacidade: float
) -> list[dict[str, object]]:
    """Reserva de 3× o gasto médio; com alvo parcial de 1× quando o prazo não cabe (Q-009-1)."""
    alvo_total = brl(regras.meses_reserva * contexto.gasto_medio)
    prazo_total = meses_para(brl(alvo_total - contexto.recursos_disponiveis), capacidade)
    cabe = prazo_total is not None and prazo_total <= prazo_objetivo

    def montar(alvo: float, prazo: int | None, parcial: bool) -> dict[str, object]:
        titulo = (
            f"Formar a primeira parte da reserva ({format_months(1)} de gasto)"
            if parcial
            else f"Formar a reserva de {format_months(regras.meses_reserva)} de gasto"
        )
        return _marco(
            TipoMarco.FORMAR_RESERVA,
            titulo=titulo,
            indicador=f"reserva de {_texto_brl(alvo)} formada e intocada",
            por_que=(
                "A reserva é o que evita voltar para a dívida quando aparece um imprevisto, e é "
                "ela que protege o dinheiro já reservado para o objetivo."
            ),
            relacao=(
                "Com a reserva de pé, o aporte do objetivo deixa de ser interrompido a cada "
                "despesa inesperada."
            ),
            valor_alvo=alvo,
            prazo_meses=prazo,
            aporte_mensal=capacidade or None,
        )

    if cabe:
        return [montar(alvo_total, prazo_total, parcial=False)]

    alvo_parcial = brl(regras.fracao_reserva_parcial * alvo_total)
    prazo_parcial = meses_para(brl(alvo_parcial - contexto.recursos_disponiveis), capacidade)
    parciais = [montar(alvo_parcial, prazo_parcial, parcial=True)]
    if prazo_total is not None and prazo_total <= regras.prazo_maximo_marco:
        parciais.append(montar(alvo_total, prazo_total, parcial=False))
    return parciais


def _marco_acumular(
    valor_alvo: float, prazo_objetivo: int, capacidade: float, regras: RegrasMarco
) -> dict[str, object] | None:
    acumulado = brl(capacidade * prazo_objetivo)
    if acumulado < regras.piso_valor_marco:
        return None
    fatia = acumulado / valor_alvo if valor_alvo > 0 else 0.0
    return _marco(
        TipoMarco.ACUMULAR_PARTE_DA_META,
        titulo="Acumular a primeira parte relevante da meta",
        indicador=f"{_texto_brl(acumulado)} acumulados para o objetivo",
        por_que=(
            f"É o que a sua capacidade sustentável de {_texto_brl(capacidade)} por mês constrói "
            f"em {format_months(prazo_objetivo)}, sem apertar o orçamento nem contar com sorte."
        ),
        relacao=(
            f"São {fatia:.0%} do objetivo já formados em patrimônio seu, que seguem valendo se o "
            "valor, o prazo ou a prioridade mudarem."
        ),
        valor_alvo=acumulado,
        prazo_meses=prazo_objetivo,
        aporte_mensal=capacidade or None,
    )


def _marco_aumentar_capacidade(
    aporte_necessario: float, capacidade: float, regras: RegrasMarco
) -> dict[str, object] | None:
    if aporte_necessario < regras.piso_valor_marco:
        return None
    return _marco(
        TipoMarco.AUMENTAR_CAPACIDADE,
        titulo="Elevar a capacidade sustentável de aporte",
        indicador=f"guardar {_texto_brl(aporte_necessario)} por mês de forma sustentável",
        por_que=(
            f"Sua capacidade hoje é de {_texto_brl(capacidade)} por mês; chegar ao aporte que o "
            "objetivo pede depende de abrir espaço no orçamento, e isso você controla."
        ),
        relacao=(
            "Com a capacidade nesse nível, o objetivo passa a caber no prazo que você pediu, sem "
            "mudar o valor da meta."
        ),
        valor_alvo=aporte_necessario,
        aporte_mensal=capacidade or None,
    )


def _marco_ajustar_prazo(
    valor_alvo: float, falta: float, capacidade: float, regras: RegrasMarco
) -> dict[str, object] | None:
    prazo = meses_para(falta, capacidade)
    if prazo is None or prazo > regras.prazo_maximo_marco or prazo < 1:
        return None
    return _marco(
        TipoMarco.AJUSTAR_PRAZO,
        titulo="Rever o prazo do objetivo, mantendo o valor",
        indicador=f"{_texto_brl(valor_alvo)} alcançados em {format_months(prazo)}",
        por_que=(
            f"Com a capacidade atual de {_texto_brl(capacidade)} por mês, este é o prazo em que o "
            "objetivo fecha sem premissa otimista nenhuma."
        ),
        relacao=(
            "O valor do objetivo continua o mesmo; o que muda é o horizonte, e ele encurta a cada "
            "marco anterior concluído."
        ),
        valor_alvo=valor_alvo,
        prazo_meses=prazo,
        aporte_mensal=capacidade or None,
    )


# ---------------------------------------------------------------------------
# Plano completo (FR-008 a FR-010, FR-024)
# ---------------------------------------------------------------------------


def planejar(
    valor_alvo: float,
    prazo_meses: int,
    contexto: ContextoFinanceiro,
    regras: RegrasMarco | None = None,
    prioridade: str | None = None,
) -> DadosPlanejarMarcos:
    """Trajetória de marcos para um objetivo que não cabe nas condições atuais.

    Sem motivo aceso, devolve trajetória vazia: não se inventa marco onde não há
    problema (FR-002).
    """
    regras = regras or RegrasMarco()
    capacidade = capacidade_sustentavel(contexto, regras)
    falta = _falta(valor_alvo, contexto)
    aporte_necessario = aporte_para(falta, prazo_meses)
    motivos = diagnosticar(valor_alvo, prazo_meses, contexto, regras)
    objetivo = ObjetivoMarco(
        valor_alvo=brl(valor_alvo), prazo_meses=prazo_meses, prioridade=prioridade
    )

    if not motivos:
        return DadosPlanejarMarcos(
            objetivo=objetivo,
            situacao=contexto,
            motivos=[],
            marcos=[],
            proximo=None,
            aporte_necessario=aporte_necessario,
            capacidade_sustentavel=capacidade,
            trajetoria_incerta=False,
            ressalvas=[],
            regras=regras,
        )

    acesos = {motivo.codigo for motivo in motivos}
    rascunhos: list[dict[str, object]] = []

    if CodigoMotivo.CAPACIDADE_INSUFICIENTE in acesos or CodigoMotivo.RISCO_EXCESSIVO in acesos:
        rascunhos.append(_marco_equilibrar_fluxo(contexto, regras))
    if CodigoMotivo.DIVIDA_A_RESOLVER in acesos:
        rascunhos.append(_marco_reduzir_divida(contexto, regras))
    if CodigoMotivo.SEM_RESERVA in acesos:
        rascunhos += _marcos_reserva(contexto, regras, prazo_meses, capacidade)
    acumulacao = {CodigoMotivo.VALOR_DISTANTE_DOS_RECURSOS, CodigoMotivo.RENDA_NAO_SUSTENTA}
    if acesos & acumulacao:
        acumular = _marco_acumular(valor_alvo, prazo_meses, capacidade, regras)
        if acumular is not None:
            rascunhos.append(acumular)
        # Pedir aporte acima do teto seguro da renda seria irresponsável.
        if CodigoMotivo.RENDA_NAO_SUSTENTA not in acesos:
            aumentar = _marco_aumentar_capacidade(aporte_necessario, capacidade, regras)
            if aumentar is not None:
                rascunhos.append(aumentar)
    prazo_viavel = meses_para(falta, capacidade)
    if CodigoMotivo.PRAZO_NAO_CABE in acesos or CodigoMotivo.PREMISSA_IRREALISTA in acesos:
        ajustar = _marco_ajustar_prazo(valor_alvo, falta, capacidade, regras)
        if ajustar is not None:
            rascunhos.append(ajustar)

    rascunhos.sort(key=lambda item: item["nivel"])  # type: ignore[arg-type,return-value]
    lista = [
        Marco(ordem=posicao, **rascunho)  # type: ignore[arg-type]
        for posicao, rascunho in enumerate(rascunhos[: regras.max_marcos], start=1)
    ]

    trajetoria_incerta = (
        capacidade <= 0
        or prazo_viavel is None
        or prazo_viavel > regras.prazo_maximo_marco
        or aporte_necessario > regras.fator_desnivel_incerto * capacidade
    )
    if trajetoria_incerta:
        # Nada de sequência artificial: com desnível grande, só o próximo passo.
        lista = lista[:1]
        for posicao, marco in enumerate(lista, start=1):
            marco.ordem = posicao

    ressalvas = [RESSALVA_NAO_GARANTE, RESSALVA_DECISAO_E_SUA] if lista else []
    if trajetoria_incerta and lista:
        ressalvas.insert(0, RESSALVA_SEM_TRAJETORIA)

    return DadosPlanejarMarcos(
        objetivo=objetivo,
        situacao=contexto,
        motivos=motivos,
        marcos=lista,
        proximo=lista[0] if lista else None,
        aporte_necessario=aporte_necessario,
        capacidade_sustentavel=capacidade,
        trajetoria_incerta=trajetoria_incerta,
        ressalvas=ressalvas,
        regras=regras,
    )


def avisos_do_plano(
    contexto: ContextoFinanceiro, regras: RegrasMarco, plano: DadosPlanejarMarcos
) -> list[str]:
    """Avisos determinísticos do envelope (specs/009 data-model)."""
    avisos = [AVISO_SEM_PATRIMONIO, AVISO_SEM_RENDIMENTO]
    if plano.marcos:
        avisos.insert(0, AVISO_MARCO_NAO_GARANTE)
    if regras.usar_saldo_atual and contexto.saldo_atual > 0:
        avisos.append(AVISO_SALDO_COMO_RECURSO)
    if contexto.saldo_atual < 0:
        avisos.append(AVISO_SALDO_NEGATIVO)
    if contexto.renda_media <= 0:
        avisos.append(AVISO_SEM_RENDA)
    return avisos
