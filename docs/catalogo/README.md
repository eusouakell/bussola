# Catálogo PF · camada de produtos da Bússola

Responde à Q3 do [contexto mestre](../contexto-spec-master.md) §20: há um
conteúdo curto de produtos, fornecido pelo time, e o agente pode citá-lo.

- **Fonte:** [`catalogo-pf.csv`](./catalogo-pf.csv), 20 linhas, recebida
  do time em 26/09/2026. Nomes de produto e links são genéricos: a PoC não
  cita nenhuma instituição real.
- **Contrato:** o subconjunto do MVP (§2) vira
  `contracts/catalogo_produtos.json` no ciclo 000
  ([contratos.md §3](../ciclos/contratos.md)).
- **Consumidores:** 002 (tema `produto` do corpus do RAG), 004
  (instrução do agente) e 005 (`simular_contratacao`).

## 1. Regras de uso

1. **Sem taxas nem condições.** O catálogo não traz taxa, rentabilidade,
   CET, parcela ou prazo comercial, e o agente não inventa nenhum deles. A
   §18 do mestre continua valendo: nada de catálogo real com taxas.
2. **Fonte oficial sempre.** Ao citar um produto, o agente mostra o link
   da coluna "Fonte oficial" e manda o cliente conferir as condições lá.
3. **Cuidado junto.** A coluna "Elegibilidade / cuidado" acompanha o
   produto em toda citação (ex.: "sem garantia de aprovação", "não promete
   contemplação").
4. **Sugestão, não oferta.** Produto entra como caminho possível para o
   objetivo, depois do diagnóstico. Crédito nunca é atalho para a meta.
5. **Ação só simulada e com consentimento.** `simular_contratacao` aceita
   apenas os produtos marcados como "ação" em §2, passa pelo gate do 005 e
   não tem efeito externo.

## 2. Recorte do MVP

Critério: serve à jornada de objetivo (Fernando juntando a entrada do
apartamento, ou outro objetivo de bem/reserva), pode ser explicado sem
taxa e não depende de chamada de rede em tempo de execução.

| `produto_id` | Produto | Uso no MVP | Onde aparece na jornada |
|---|---|---|---|
| `reserva_objetivo` | Reserva por objetivo | RAG + ação | AGIR: separar o aporte do cenário escolhido numa meta |
| `controle_gastos` | Controle de Gastos | RAG + ação | AGIR e ACOMPANHAR: limite nas categorias dos cortes sugeridos |
| `credito_imobiliario` | Crédito Imobiliário | RAG + ação | ORIENTAR: caminho com financiamento depois da entrada. Sem parcela calculada, sem promessa de aprovação |
| `consorcio_imoveis` | Consórcio de Imóveis | RAG + ação | ORIENTAR: alternativa quando o prazo é flexível. Explica sorteio e lance |
| `consorcio_veiculos` | Consórcio de Veículos | RAG + ação | ORIENTAR, quando o objetivo é um carro |
| `renegociacao` | Renegociação de dívidas | RAG + ação | ENTENDER: juros e parcelas pesam antes de acelerar o objetivo |
| `cdb_renda_fixa` | CDB / renda fixa | Só RAG | ORIENTAR: educação sobre prazo e liquidez da reserva |
| `lci_lca` | LCI / LCA | Só RAG | ORIENTAR: educação sobre prazo, liquidez e tributação |

- **CDB e LCI/LCA ficam sem ação:** investimento exige perfil de investidor
  (adequação), que a base não tem. O agente só explica a diferença entre
  as alternativas, sem valor futuro nem recomendação.
- **Crédito Imobiliário:** a planilha pede "entrada/parcela/prazo
  estimados". Sem taxa, a Bússola calcula só o que vem da base (quanto e em
  quanto tempo junta a entrada) e aponta o simulador oficial para o resto.
  É o item 4 do card de AGIR no design ("Simular um financiamento · sem
  taxas").

## 3. Fora do MVP

| Produto | Motivo |
|---|---|
| Open Finance | Não objetivo do mestre §18. No design aparece só como card desabilitado "em breve" |
| Cartões PF / rotativo, Contas PF / tarifas, Empréstimos PF, Financiamentos PF | Dependem das APIs públicas `api.exemplo.test/open-banking/opendata-*`: trazem taxas e tarifas (§18) e criam dependência de rede na demo. Evolução natural da camada |
| Empréstimo pessoal, Consignado CLT, Crédito com Garantia de Imóvel, Crédito para Investidores, Crédito Sob Medida | Crédito não é atalho para o objetivo, e a elegibilidade depende de dados que a base não tem (margem, garantia, patrimônio, contratos) |
| Limite Garantido, Simular Compra Futura | Não servem à jornada de objetivo; risco de incentivar endividamento |

## 4. Coluna "Persona / readiness"

A planilha segmenta por outras personas (Renata, Diego, Marcos, Beatriz) e
estágios (SANEAR, ACUMULAR, OTIMIZAR). A Bússola não usa essa segmentação:
a persona da demo é o Fernando, e a relevância de cada produto vem da
jornada e das ferramentas (ex.: `dividas_e_parcelas` para a renegociação).
A coluna fica no CSV como referência.
