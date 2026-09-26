// Etapa ACOMPANHAR: divisor de mês, planejado × realizado, rota recalculada,
// oportunidade de folga, recibo de ação e status do plano.
import { useId, useState } from "react";
import { avisosDe, dadosDe, fonteDe } from "../../agente/envelope";
import type { Dados, Envelope } from "../../agente/tipos";
import { brl, mesAbrev, mesExtenso, meses, nomeMes, percentual } from "../../formatacao/formatar";
import type { ItemCard, ItemDivisorMes } from "../../sessao/modelo";
import { Avisos } from "../base/Avisos";
import { ChipFonte } from "../base/ChipFonte";
import { Icone } from "../base/Icone";
import { lista, num, obj, txt } from "./ler";
import { CabecalhoCard, Kpi, larguraMedidor } from "./partes";

export function DivisorMes({ item }: { item: ItemDivisorMes }) {
  const texto = `${mesExtenso(item.anomes).replace(/^./, (c) => c.toUpperCase())} liberado`;
  return (
    <div className="month-div" role="separator" aria-label={texto}>
      <span className="ln" />
      <span className="month-pill glass-chrome">
        <Icone nome="calendario" tamanho="sm" />
        {texto}
      </span>
      <span className="ln" />
    </div>
  );
}

const STATUS_MES: Record<string, { rotulo: string; classe: string }> = {
  no_plano: { rotulo: "No plano", classe: "badge badge-ok" },
  desvio: { rotulo: "Abaixo do plano", classe: "badge badge-warn" },
  folga: { rotulo: "Acima do plano", classe: "badge badge-ok" },
};

/** Envelope aninhado (`resumo_mes` dentro de `avancar_mes`). */
function envelopeAninhado(d: Dados | undefined): Envelope | undefined {
  const fonte = obj(d, "fonte");
  if (!d || !fonte || typeof fonte.ferramenta !== "string") return undefined;
  return { dados: obj(d, "dados") ?? {}, fonte: fonte as unknown as Envelope["fonte"], avisos: Array.isArray(d.avisos) ? (d.avisos as string[]) : [] };
}

export function CardPlanejadoRealizado({ item }: { item: ItemCard }) {
  const dados = dadosDe(item.resposta);
  const anomes = num(dados, "anomes");
  const status = txt(dados, "status") ?? "no_plano";
  const info = STATUS_MES[status] ?? STATUS_MES.no_plano;
  const tomDesvio = status === "desvio" ? "warn" : status === "folga" ? "ok" : undefined;
  const causa = obj(dados, "categoria_desvio");
  const resumo = envelopeAninhado(obj(dados, "resumo_mes"));
  const desvio = num(dados, "desvio");
  return (
    <article className="glass-card card-pad enter" aria-label="CardPlanejadoRealizado">
      <CabecalhoCard tag="diagnostico" resposta={item.resposta} />
      <div className="row-between">
        <span className="t-title">{anomes ? `${nomeMes(anomes)}: planejado × realizado` : "Planejado × realizado"}</span>
        <span className={info.classe}>{info.rotulo}</span>
      </div>
      <div className="grid-kpi">
        <Kpi rotulo="Planejado" valor={brl(num(dados, "planejado"))} />
        <Kpi rotulo="Realizado" valor={brl(num(dados, "realizado"))} />
        <Kpi rotulo="Diferença" valor={`${desvio !== undefined && desvio > 0 ? "+" : ""}${brl(desvio)}`} tom={tomDesvio} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div className="row-between">
          <span className="small" style={{ fontWeight: 800, color: "var(--ink)" }}>
            Progresso da meta
          </span>
          <span className="small num">
            {percentual(num(dados, "percentual"))} · {brl(num(dados, "acumulado"))} guardados
          </span>
        </div>
        <div className={`meter lg ${status === "desvio" ? "warn" : status === "folga" ? "ok" : "accent"}`} aria-hidden="true">
          <span style={{ width: larguraMedidor(num(dados, "percentual")) }} />
        </div>
        <span className="small num">
          Faltam {brl(num(dados, "restante"))} · {meses(num(dados, "meses_restantes"))} de prazo
        </span>
      </div>
      {causa && (
        <div className="note note-warn" style={{ fontSize: 14.5, lineHeight: "20px", padding: "10px 12px" }}>
          <Icone nome="alerta" />
          <span>
            <strong>Causa principal:</strong> {txt(causa, "macro")}: <span className="num">{brl(num(causa, "valor_mes"))}</span> no mês (média{" "}
            <span className="num">{brl(num(causa, "media_base"))}</span>, <span className="num">+{brl(num(causa, "aumento"))}</span>).
          </span>
        </div>
      )}
      <div className="row-between">
        <span className="small num">Tolerância do plano: {brl(num(dados, "tolerancia"))} para mais ou para menos</span>
        {resumo && <ChipFonte fonte={resumo.fonte} avisos={resumo.avisos} />}
      </div>
      <Avisos avisos={avisosDe(item.resposta)} />
    </article>
  );
}

interface AcaoProps {
  item: ItemCard;
  onEnviar: (texto: string) => void;
  ocupado: boolean;
}

export function CardRotaRecalculada({ item, onEnviar, ocupado }: AcaoProps) {
  const dados = dadosDe(item.resposta);
  const rotas = lista(dados, "rotas");
  const [escolha, setEscolha] = useState(txt(rotas[0], "id") ?? "A");
  const grupo = useId();
  const anomes = num(dados, "anomes");
  return (
    <article className="glass-card card-pad enter" aria-label="CardRotaRecalculada" style={{ animationDelay: ".12s" }}>
      <CabecalhoCard tag="recomendacao" resposta={item.resposta} />
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Icone nome="trilha" estilo={{ color: "var(--tag-rec)" }} />
        <span className="t-title">Recalculei sua rota para recuperar o desvio</span>
      </div>
      <div role="radiogroup" aria-label="Rotas possíveis" className="grid-2">
        {rotas.map((r) => {
          const id = txt(r, "id") ?? "";
          const sel = id === escolha;
          return (
            <label key={id} className={sel ? "opt sel" : "opt"}>
              <input
                type="radio"
                name={grupo}
                value={id}
                checked={sel}
                onChange={() => setEscolha(id)}
                className="sr-only"
              />
              <span className="radio" aria-hidden="true" />
              <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 17, fontWeight: 900 }}>
                  {id}) {txt(r, "titulo")}
                </span>
                <span className="num" style={{ fontSize: 15.5, fontWeight: 800 }}>
                  {brl(num(r, "aporte_mensal"))}/mês por {meses(num(r, "prazo_meses"))}
                </span>
                {txt(r, "descricao") && <span className="small">{txt(r, "descricao")}</span>}
                {num(r, "prazo_total_meses") !== undefined && (
                  <span className="small num">Plano total: {meses(num(r, "prazo_total_meses"))}</span>
                )}
              </span>
            </label>
          );
        })}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" disabled={ocupado || rotas.length === 0} onClick={() => onEnviar(`Quero adotar a rota ${escolha}`)}>
          Adotar nova rota
        </button>
        <span className="small" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Icone nome="escudo" tamanho="sm" />
          Abre um pedido de autorização
        </span>
      </div>
      {anomes !== undefined && <span className="sr-only">Rotas calculadas em {mesAbrev(anomes)}</span>}
    </article>
  );
}

export function CardOportunidade({ item, onEnviar, ocupado }: AcaoProps) {
  const dados = dadosDe(item.resposta);
  return (
    <article className="glass-card card-pad enter" aria-label="Oportunidade no mês" style={{ animationDelay: ".12s" }}>
      <CabecalhoCard tag="recomendacao" textoTag="Oportunidade" resposta={item.resposta} />
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span className="t-title">Sobrou além do plano</span>
        <span className="kpi num" style={{ color: "var(--ok)" }}>
          +{brl(num(dados, "desvio"))}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div className="meter lg ok" aria-hidden="true">
          <span style={{ width: larguraMedidor(num(dados, "percentual")) }} />
        </div>
        <span className="small num">
          Meta em {percentual(num(dados, "percentual"))} · {brl(num(dados, "acumulado"))} guardados
        </span>
      </div>
      <p className="prose" style={{ fontSize: 16 }}>
        Você pode deixar essa sobra no objetivo e chegar antes, ou manter o plano como está.
      </p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-secondary btn-sm" disabled={ocupado} onClick={() => onEnviar("Ver status do plano")}>
          Ver status do plano
        </button>
      </div>
    </article>
  );
}

/** Resultado de ação executada (lembretes, simulação de contratação, ajuste). */
export function ReciboAcao({ item }: { item: ItemCard }) {
  const dados = dadosDe(item.resposta);
  return (
    <div className="receipt ok enter" role="status" aria-label="Ação concluída">
      <span className="st" style={{ background: "var(--ok)", color: "#fff" }}>
        <Icone nome="check" tamanho="sm" traco={3} />
      </span>
      <span style={{ flex: "1 1 auto", minWidth: 0 }}>{txt(dados, "mensagem") ?? "Ação concluída."}</span>
      <ChipFonte fonte={fonteDe(item.resposta)} avisos={avisosDe(item.resposta)} compacto />
    </div>
  );
}

const STATUS_HIST: Record<string, string> = { no_plano: "No plano", desvio: "Abaixo", folga: "Acima" };

export function CardStatusPlano({ item }: { item: ItemCard }) {
  const dados = dadosDe(item.resposta);
  const plano = obj(dados, "plano");
  const objetivo = obj(dados, "objetivo");
  const historico = lista(dados, "historico");
  return (
    <article className="glass-card card-pad enter" aria-label="CardStatusPlano">
      <CabecalhoCard tag="diagnostico" textoTag="Status do plano" resposta={item.resposta} />
      <span className="t-title">{txt(objetivo, "descricao") ?? "Seu plano"}</span>
      <div className="grid-kpi">
        <Kpi rotulo="Guardado" valor={brl(num(dados, "acumulado"))} />
        <Kpi rotulo="Falta" valor={brl(num(dados, "restante"))} />
        <Kpi rotulo="Aporte" valor={brl(num(plano, "aporte_mensal"))} sufixo="/mês" />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div className="row-between">
          <span className="small" style={{ fontWeight: 800, color: "var(--ink)" }}>
            Progresso
          </span>
          <span className="small num">
            {percentual(num(dados, "percentual"))} de {brl(num(plano, "valor_alvo"))}
          </span>
        </div>
        <div className="meter lg accent" aria-hidden="true">
          <span style={{ width: larguraMedidor(num(dados, "percentual")) }} />
        </div>
      </div>
      {historico.length > 0 && (
        <table className="tabela-hist">
          <caption className="sr-only">Histórico mês a mês</caption>
          <thead>
            <tr>
              <th scope="col">Mês</th>
              <th scope="col">Planejado</th>
              <th scope="col">Realizado</th>
              <th scope="col">Situação</th>
            </tr>
          </thead>
          <tbody>
            {historico.map((h) => (
              <tr key={num(h, "anomes")}>
                <th scope="row">{mesAbrev(num(h, "anomes"))}</th>
                <td className="num">{brl(num(h, "planejado"))}</td>
                <td className="num">{brl(num(h, "realizado"))}</td>
                <td>{STATUS_HIST[txt(h, "status") ?? ""] ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <Avisos avisos={avisosDe(item.resposta)} />
    </article>
  );
}
