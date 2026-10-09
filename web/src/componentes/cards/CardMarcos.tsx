// Marcos financeiros intermediários (ciclo 009): situação atual, próximo marco
// em destaque, trajetória e ressalvas. Todo número vem do envelope de
// `planejar_marcos`; o card nunca calcula nem estima nada.
import { avisosDe, dadosDe } from "../../agente/envelope";
import { brl, meses } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { DISCLAIMER_SIMULACAO, Disclaimer } from "../base/Disclaimer";
import { Icone } from "../base/Icone";
import { bool, lista, num, obj, textos, txt } from "./ler";
import { CabecalhoCard, Kpi, larguraMedidor } from "./partes";

/** Valor e prazo do marco, do jeito que a ferramenta mandou (ou "—"). */
function metaDoMarco(marco: Record<string, unknown>): string {
  const valor = num(marco, "valor_alvo");
  const prazo = num(marco, "prazo_meses");
  const partes = [valor !== undefined ? brl(valor) : undefined, prazo !== undefined ? meses(prazo) : undefined];
  const texto = partes.filter(Boolean).join(" · ");
  return texto || "—";
}

export function CardMarcos({ item }: { item: ItemCard }) {
  const dados = dadosDe(item.resposta);
  const objetivo = obj(dados, "objetivo");
  const proximo = obj(dados, "proximo");
  const marcos = lista(dados, "marcos");
  const motivos = lista(dados, "motivos");
  const ressalvas = textos(dados, "ressalvas");
  const incerta = bool(dados, "trajetoria_incerta") === true;
  const aporte = num(dados, "aporte_necessario");
  const capacidade = num(dados, "capacidade_sustentavel");
  const seguintes = marcos.filter((m) => num(m, "ordem") !== num(proximo, "ordem"));
  const largura = larguraMedidor(aporte && capacidade ? (capacidade / aporte) * 100 : undefined);

  return (
    <article className="glass-card card-pad enter" aria-label="CardMarcos">
      <CabecalhoCard tag="recomendacao" textoTag="Primeira etapa" resposta={item.resposta} />

      {objetivo && (
        <span className="prose" style={{ fontWeight: 700, color: "var(--ink-2)" }}>
          Objetivo de <strong className="num">{brl(num(objetivo, "valor_alvo"))}</strong> em{" "}
          <strong className="num">{meses(num(objetivo, "prazo_meses"))}</strong>
          {motivos.length > 0 ? ". Hoje, o valor mensal necessário ultrapassa o que os dados indicam como disponível." : "."}
        </span>
      )}

      {aporte !== undefined && capacidade !== undefined && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div className="meter lg" aria-hidden="true">
            <span style={{ width: largura, background: "var(--tag-sim)" }} />
          </div>
          <div className="row-between">
            <span className="small num">Dinheiro disponível por mês, segundo o histórico: {brl(capacidade)}</span>
            <span className="small num">Para atingir o prazo, seria preciso guardar: {brl(aporte)}/mês</span>
          </div>
        </div>
      )}

      {motivos.length > 0 && (
        <details className="cenario-detalhes">
          <summary>Por que sugerimos começar por uma etapa menor?</summary>
          <ul
          style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 4 }}
          aria-label="Situação atual"
        >
          {motivos.map((motivo, i) => (
            <li key={txt(motivo, "codigo") ?? i} className="small" style={{ display: "flex", gap: 8 }}>
              <Icone nome="info" tamanho="sm" />
              <span>{txt(motivo, "explicacao") ?? txt(motivo, "codigo")}</span>
            </li>
          ))}
        </ul>
        </details>
      )}

      {proximo && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }} aria-label="Próximo marco">
          <div style={{ display: "flex", alignItems: "flex-end", gap: 16, flexWrap: "wrap" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: "1 1 auto", minWidth: 0 }}>
              <span className="kpi-label">
                <Icone nome="estrela" tamanho="sm" /> Primeira etapa
              </span>
              <span style={{ fontSize: 17, fontWeight: 800 }}>{txt(proximo, "titulo") ?? "—"}</span>
              <span className="small">{txt(proximo, "indicador") ?? ""}</span>
            </div>
            <Kpi rotulo="Valor e prazo" valor={<span className="num">{metaDoMarco(proximo)}</span>} />
          </div>
          {txt(proximo, "por_que") && <p className="prose" style={{ margin: 0 }}>{txt(proximo, "por_que")}</p>}
          {txt(proximo, "relacao_com_objetivo") && (
            <p className="small" style={{ margin: 0 }}>{txt(proximo, "relacao_com_objetivo")}</p>
          )}
        </div>
      )}

      {seguintes.length > 0 && (
        <details className="cenario-detalhes">
          <summary>Ver as próximas etapas</summary>
          <ul
          style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}
          aria-label="Marcos seguintes"
        >
          {seguintes.map((marco, i) => (
            <li key={`${txt(marco, "tipo") ?? "marco"}-${i}`} className="linha-lista">
              <span className="nome">
                <span>
                  {num(marco, "ordem") ?? i + 2}. {txt(marco, "titulo") ?? "—"}
                </span>
                <span className="small">{txt(marco, "indicador") ?? ""}</span>
              </span>
              <span className="valor num">{metaDoMarco(marco)}</span>
            </li>
          ))}
        </ul>
        </details>
      )}

      {ressalvas.length > 0 && (
        <div
          className={incerta ? "note note-warn" : "note note-info"}
          style={{ fontSize: 14.5, lineHeight: "20px", padding: "10px 12px" }}
          aria-label="Ressalvas"
        >
          <Icone nome={incerta ? "alerta" : "info"} />
          <span>{ressalvas.join(" ")}</span>
        </div>
      )}

      <Avisos avisos={avisosDe(item.resposta)} />
      <Disclaimer>{DISCLAIMER_SIMULACAO}</Disclaimer>
    </article>
  );
}
