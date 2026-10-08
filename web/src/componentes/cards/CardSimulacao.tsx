// Simulação: mostrar a decisão antes dos detalhes estatísticos.
import { avisosDe, dadosDe } from "../../agente/envelope";
import { brl, fracaoPercentual, meses } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { DISCLAIMER_SIMULACAO, Disclaimer } from "../base/Disclaimer";
import { bool, num, obj, txt } from "./ler";

function explicarCondicoes(p: Record<string, unknown> | undefined): string[] {
  if (!p) return [];
  const lista: string[] = [];
  const rendimento = num(p, "rendimento_mensal");
  if (rendimento !== undefined) lista.push(rendimento === 0 ? "Sem considerar rendimentos." : `Considerando rendimento de ${fracaoPercentual(rendimento)} ao mês.`);
  const saldoAtual = bool(p, "usar_saldo_atual");
  if (saldoAtual === false) lista.push("Sem contar dinheiro que você já tem guardado.");
  if (saldoAtual === true) lista.push(`Inclui ${brl(num(p, "saldo_inicial"))} já guardados.`);
  if (txt(p, "base_capacidade") === "sobra_mediana") {
    const n = num(p, "meses_considerados");
    lista.push(n !== undefined
      ? `O valor disponível por mês foi estimado a partir de ${meses(n)} do seu histórico.`
      : "O valor disponível por mês foi estimado a partir do seu histórico.");
  }
  return lista;
}

export function CardSimulacao({ item }: { item: ItemCard }) {
  const dados = dadosDe(item.resposta);
  const premissas = obj(dados, "premissas");
  const valor = num(dados, "valor_alvo");
  const aporte = num(dados, "aporte_mensal");
  const prazo = num(dados, "prazo_meses");
  const capacidade = num(premissas, "capacidade_mensal");
  const folga = num(dados, "folga_mensal");
  const viavel = bool(dados, "viavel");
  const modoAporte = txt(dados, "modo") === "aporte";
  const condicoes = explicarCondicoes(premissas);

  return (
    <article className="glass-card card-pad enter resumo-simulacao" aria-label="Simulação do objetivo financeiro">
      <h3 className="t-title">{modoAporte ? "Quando você pode chegar à meta" : "Quanto guardar por mês"}</h3>
      <strong className="resumo-orcamento-valor num">
        {modoAporte ? meses(prazo) : brl(aporte)}
      </strong>
      <p className="small">
        {modoAporte
          ? `Se você guardar ${brl(aporte)} por mês para chegar a ${brl(valor)}.`
          : `Estimativa para juntar ${brl(valor)} em ${meses(prazo)}.`}
      </p>
      {viavel === false && (
        <p className="cenario-alerta" role="note">Esse valor é maior do que o dinheiro que costuma sobrar no mês.</p>
      )}
      {viavel === true && (
        <p className="cenario-estado">Pelo histórico, esse valor cabe no dinheiro que costuma sobrar.</p>
      )}
      {(condicoes.length > 0 || capacidade !== undefined || folga !== undefined) && (
        <details className="cenario-detalhes">
          <summary>Confira como calculamos</summary>
          <div className="cenario-detalhes-corpo">
            {capacidade !== undefined && <p>Dinheiro que costuma sobrar por mês: {brl(capacidade)}.</p>}
            {folga !== undefined && (
              <p>{folga >= 0
                ? `Depois de guardar esse valor, sobrariam cerca de ${brl(folga)} no mês.`
                : `Faltariam cerca de ${brl(Math.abs(folga))} por mês para seguir esse plano.`}</p>
            )}
            {condicoes.map((condicao) => <p key={condicao}>{condicao}</p>)}
            <p>Isso é uma simulação, e o dinheiro disponível pode variar de um mês para outro.</p>
          </div>
        </details>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
      <Disclaimer>{DISCLAIMER_SIMULACAO}</Disclaimer>
    </article>
  );
}
