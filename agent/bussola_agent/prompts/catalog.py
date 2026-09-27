"""Curated product catalog embedded in the instruction (spec FR-006, D-05).

Copy of ``contracts/catalogo_produtos.json`` (``docs/catalogo/`` §1). The agent
image copies only ``agent/``, so the catalog lives here; a test keeps it equal
to the contract file. The render carries name, use, caution and official link,
never rates or conditions, and has no braces (ADK instruction templating).
"""

from typing import Final

CATALOG: Final[tuple[dict[str, str | bool], ...]] = (
    {
        "acao_simulada": True,
        "categoria": "Metas & reserva",
        "cuidado": "Não hardcodar rentabilidade se não consultada em fonte atual",
        "fonte_oficial": "https://www.bcb.gov.br/cidadaniafinanceira",
        "nome": "Reserva por objetivo",
        "produto_id": "reserva_objetivo",
        "uso": "Criar meta/reserva e acompanhar objetivo",
    },
    {
        "acao_simulada": True,
        "categoria": "Dados & contexto",
        "cuidado": "Não impor corte; cliente escolhe",
        "fonte_oficial": "https://www.bcb.gov.br/cidadaniafinanceira",
        "nome": "Controle de Gastos",
        "produto_id": "controle_gastos",
        "uso": "Categorizar gastos, definir controles e alertas por categoria",
    },
    {
        "acao_simulada": True,
        "categoria": "Moradia",
        "cuidado": "Sem garantia de aprovação; condições atuais devem vir de simulador/fonte",
        "fonte_oficial": "https://www.planalto.gov.br/ccivil_03/leis/l8004.htm",
        "nome": "Crédito Imobiliário",
        "produto_id": "credito_imobiliario",
        "uso": "Comparar caminho de compra com financiamento",
    },
    {
        "acao_simulada": True,
        "categoria": "Moradia / bens",
        "cuidado": "Não prometer contemplação; explicar sorteio/lance",
        "fonte_oficial": "https://www.procon.sp.gov.br/consorcio/",
        "nome": "Consórcio de Imóveis",
        "produto_id": "consorcio_imoveis",
        "uso": "Alternativa quando há flexibilidade de prazo",
    },
    {
        "acao_simulada": True,
        "categoria": "Bens",
        "cuidado": "Não prometer contemplação",
        "fonte_oficial": "https://www.procon.sp.gov.br/consorcio/",
        "nome": "Consórcio de Veículos",
        "produto_id": "consorcio_veiculos",
        "uso": "Planejar compra de veículo sem financiamento tradicional",
    },
    {
        "acao_simulada": True,
        "categoria": "Dívida",
        "cuidado": "Condições são personalizadas; não inventar desconto/taxa",
        "fonte_oficial": "https://desenrola.gov.br/",
        "nome": "Renegociação de dívidas",
        "produto_id": "renegociacao",
        "uso": "Reorganizar dívida antes de acelerar objetivo",
    },
    {
        "acao_simulada": False,
        "categoria": "Investimentos",
        "cuidado": "Taxa deve vir de fonte atual; não recomendar sem perfil/adequação",
        "fonte_oficial": "https://www.gov.br/investidor/pt-br/investir/tipos-de-investimentos/titulos-bancarios",
        "nome": "CDB / renda fixa",
        "produto_id": "cdb_renda_fixa",
        "uso": "Alocar reserva/meta conforme prazo e liquidez",
    },
    {
        "acao_simulada": False,
        "categoria": "Investimentos",
        "cuidado": "Liquidez/prazo/tributação precisam ser explicitados",
        "fonte_oficial": "https://www.gov.br/investidor/pt-br/investir/tipos-de-investimentos/titulos-bancarios/letra-de-credito-imobiliario-lci-e-letra-de-credito-do-agronegocio-lca",
        "nome": "LCI / LCA",
        "produto_id": "lci_lca",
        "uso": "Alternativa de renda fixa para objetivo",
    },
)


def render_catalog() -> str:
    """One line per product: name, category, use, caution and official link."""
    lines = []
    for item in CATALOG:
        simulated = " Tem ação simulada na demonstração." if item["acao_simulada"] else ""
        lines.append(
            f"- {item['nome']} ({item['categoria']}). Para que serve: {item['uso']}. "
            f"Cuidado: {item['cuidado']}.{simulated} Fonte oficial: {item['fonte_oficial']}"
        )
    return "\n".join(lines)
