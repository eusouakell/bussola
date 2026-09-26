// Peças comuns das vistas P1–P5: selo de status (texto + ícone), KPI com
// chip de fonte e botão de ação que só manda texto ao agente.
import type { CSSProperties, ReactNode } from "react";
import { avisosDe, dadosDe, fonteDe } from "../agente/envelope";
import { ChipFonte } from "../componentes/base/ChipFonte";
import { Icone, type NomeIcone } from "../componentes/base/Icone";
import { num } from "../componentes/cards/ler";
import { brl, nomeMes } from "../formatacao/formatar";
import type { PlanoLido, Resposta, StatusMes } from "./dados";

const STATUS: Record<StatusMes, { rotulo: string; classe: string; icone: NomeIcone }> = {
  no_plano: { rotulo: "No plano", classe: "badge badge-ok", icone: "check" },
  desvio: { rotulo: "Abaixo do plano", classe: "badge badge-warn", icone: "alerta" },
  folga: { rotulo: "Acima do plano", classe: "badge badge-ok", icone: "estrela" },
};

/** Status do mês com texto e ícone (FR-030: nunca só cor). */
export function SeloStatus({ status }: { status: StatusMes | undefined }) {
  if (!status) {
    return (
      <span className="badge badge-neutral">
        <Icone nome="calendario" tamanho="sm" />
        Plano ativo
      </span>
    );
  }
  const info = STATUS[status];
  return (
    <span className={info.classe}>
      <Icone nome={info.icone} tamanho="sm" />
      {info.rotulo}
    </span>
  );
}

export function tomStatus(status: StatusMes | undefined): "warn" | "ok" | "accent" {
  return status === "desvio" ? "warn" : status === "folga" ? "ok" : "accent";
}

/** Chip de fonte a partir da resposta de origem; some quando não há envelope. */
export function Fonte({ origem, compacto, rotulo }: { origem: Resposta | undefined; compacto?: boolean; rotulo?: string }) {
  return <ChipFonte fonte={fonteDe(origem?.resposta)} avisos={avisosDe(origem?.resposta)} compacto={compacto} rotulo={rotulo} />;
}

/** Chips das origens distintas de uma linha que combina números de mais de uma resposta. */
export function Fontes({ origens, compacto }: { origens: (Resposta | undefined)[]; compacto?: boolean }) {
  const unicas = origens.filter((o, i): o is Resposta => !!o && origens.findIndex((x) => x?.chamadaId === o.chamadaId) === i);
  if (unicas.length === 0) return null;
  return (
    <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
      {unicas.map((o) => (
        <Fonte key={o.chamadaId} origem={o} compacto={compacto} />
      ))}
    </span>
  );
}

interface KpiFonteProps {
  rotulo: string;
  valor: string;
  sufixo?: string;
  origem: Resposta | undefined;
}

/** Caixa de KPI com o chip de fonte do envelope de onde o número veio. */
export function KpiFonte({ rotulo, valor, sufixo, origem }: KpiFonteProps) {
  return (
    <div className="kpi-box" style={{ gap: 6 }}>
      <div className="row-between" style={{ flexWrap: "nowrap", gap: 6 }}>
        <span className="kpi-label">{rotulo}</span>
        <Fonte origem={origem} compacto />
      </div>
      <span className="kpi num" style={{ fontSize: 22, lineHeight: "28px" }}>
        {valor}
        {sufixo && <span style={{ fontSize: 14, fontWeight: 800, color: "var(--ink-2)" }}>{sufixo}</span>}
      </span>
    </div>
  );
}

interface AcaoProps {
  children: ReactNode;
  onClick: () => void;
  primario?: boolean;
  icone?: NomeIcone;
  estilo?: CSSProperties;
}

/** Botão de ação (mínimo de 44 px): navega ou manda um texto ao agente. */
export function BotaoAcao({ children, onClick, primario, icone, estilo }: AcaoProps) {
  return (
    <button
      type="button"
      className={primario ? "btn btn-primary" : "btn btn-secondary btn-sm"}
      onClick={onClick}
      style={{
        width: "100%",
        height: "auto",
        minHeight: primario ? 48 : 44,
        whiteSpace: "normal",
        paddingTop: 8,
        paddingBottom: 8,
        textAlign: "center",
        ...estilo,
      }}
    >
      {icone && <Icone nome={icone} tamanho="sm" />}
      {children}
    </button>
  );
}

const NOTA = { fontSize: 14, lineHeight: "19px", padding: "9px 12px" };

/** Nota do último mês acompanhado (`avancar_mes`): status e diferença que a ferramenta devolveu. */
export function NotaUltimoMes({ plano }: { plano: PlanoLido }) {
  if (!plano.ultimoMes) return null;
  const dados = dadosDe(plano.ultimoMes.resposta);
  const anomes = num(dados, "anomes");
  const desvio = num(dados, "desvio");
  const status = plano.ultimoStatus;
  const texto =
    status === "desvio"
      ? `Fechou abaixo do planejado: diferença de ${brl(desvio)}. As rotas para voltar à trilha estão na conversa.`
      : status === "folga"
        ? `Fechou acima do planejado: diferença de +${brl(desvio)}.`
        : "Fechou dentro da tolerância do plano.";
  return (
    <article className="glass-card enter" aria-label="Último mês" style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="row-between">
        <span className="t-title" style={{ fontSize: 16 }}>
          {anomes ? nomeMes(anomes) : "Último mês"}
        </span>
        <Fonte origem={plano.ultimoMes} />
      </div>
      <div
        className={status === "desvio" ? "note note-warn" : "note"}
        style={status === "desvio" ? NOTA : { ...NOTA, background: "var(--ok-soft)", color: "var(--ok)" }}
      >
        <Icone nome={status === "desvio" ? "alerta" : "check"} />
        <span className="num">{texto}</span>
      </div>
    </article>
  );
}
