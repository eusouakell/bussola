// Bastidores (FR-016–FR-018): o agente por dentro. Painel lateral no desktop e
// bottom sheet no mobile, com Jornada, Ferramentas, Consentimentos e Auditoria.
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Consentimento } from "../../agente/tipos";
import { CONFIG } from "../../config";
import { brl, hora, horaSegundos, mascararArgs, mascararId, mesAbrev, periodo } from "../../formatacao/formatar";
import type { EventoAuditoria, ModeloSessao, RegistroFerramenta, TipoEventoAuditoria } from "../../sessao/modelo";
import { Icone } from "../base/Icone";
import { passosJornada } from "../jornada/StepperJornada";

export const ABAS = ["Jornada", "Ferramentas", "Consentimentos", "Auditoria"] as const;
export type Aba = (typeof ABAS)[number];

const ABAS_CURTAS: Record<Aba, string> = {
  Jornada: "Jornada",
  Ferramentas: "Ferram.",
  Consentimentos: "Consent.",
  Auditoria: "Auditoria",
};

function AbaJornada({ modelo }: { modelo: ModeloSessao }) {
  const passos = passosJornada(modelo.estado.estado_jornada);
  const entrada = new Map(modelo.jornada.map((p) => [p.estado, p.ts]));
  return (
    <>
      <ol style={{ listStyle: "none", margin: 0, padding: 0 }} aria-label="Estados da jornada">
        {passos.map((p, i) => {
          const ts = entrada.get(p.estado);
          return (
            <li key={p.estado} className={i === passos.length - 1 ? "tl-item last" : "tl-item"}>
              <span className={`tl-dot ${p.situacao}`} aria-hidden="true" />
              <div className="tl-main">
                <div className="tl-title">
                  <span>{p.estado}</span>
                  <span className="mono" style={{ color: "var(--ink-3)" }}>
                    {ts !== undefined && p.situacao !== "next" ? horaSegundos(ts) : "—"}
                  </span>
                </div>
                <span className="tl-sub">
                  {p.situacao === "done" ? "concluído" : p.situacao === "now" ? "estado atual" : "próximo"}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="p-card">
        <span className="mono" style={{ fontWeight: 600 }}>
          session.state.objetivo
        </span>
        <pre className="mono">{JSON.stringify(modelo.estado.objetivo ?? null, null, 2)}</pre>
      </div>
    </>
  );
}

function BadgeFerramenta({ f }: { f: RegistroFerramenta }) {
  const estilo = { height: 24, fontSize: 12 };
  if (f.status === "consultando") {
    return (
      <span className="badge badge-neutral" style={estilo}>
        <span className="spin" style={{ width: 12, height: 12, borderWidth: 2 }} aria-hidden="true" />
        executando
      </span>
    );
  }
  const duracao = f.fim !== undefined ? ` · ${Math.max(0, Math.round(f.fim - f.inicio))} ms` : "";
  if (f.status === "erro") {
    return (
      <span className="badge badge-err" style={estilo}>
        <Icone nome="x" tamanho="sm" />
        {f.codigoErro ?? "erro"}
        {duracao}
      </span>
    );
  }
  return (
    <span className="badge badge-ok" style={estilo}>
      ok{duracao}
    </span>
  );
}

function AbaFerramentas({ modelo }: { modelo: ModeloSessao }) {
  if (modelo.ferramentas.length === 0) {
    return <p className="tl-sub">Nenhuma ferramenta chamada ainda. Conte um objetivo na conversa.</p>;
  }
  const ultima = modelo.ferramentas.length - 1;
  return (
    <>
      {modelo.ferramentas.map((f, i) => {
        const args = Object.entries(mascararArgs(f.args));
        return (
          <div key={f.chamadaId} className={i === ultima && f.status === "consultando" ? "p-card new" : "p-card"}>
            <div className="row-between">
              <span className="mono" style={{ fontWeight: 600 }}>
                {f.nome}
              </span>
              <BadgeFerramenta f={f} />
            </div>
            {args.length > 0 && (
              <span className="tl-sub mono">{args.map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join(" · ")}</span>
            )}
            {f.fonte && (
              <span className="tl-sub">
                {f.fonte.tabelas.length > 0 ? f.fonte.tabelas.join(", ") : "sem tabela (local)"} · {periodo(f.fonte.periodo)}
              </span>
            )}
            {f.avisos.map((a) => (
              <span key={a} className="tl-sub" style={{ color: "var(--warn)", fontWeight: 800 }}>
                aviso: {a}
              </span>
            ))}
          </div>
        );
      })}
    </>
  );
}

const ROTULO_STATUS: Record<Consentimento["status"], { classe: string; texto: string }> = {
  pendente: { classe: "badge-warn", texto: "pendente" },
  aceito: { classe: "badge-ok", texto: "aceito" },
  recusado: { classe: "badge-neutral", texto: "recusado" },
};

function AbaConsentimentos({ modelo }: { modelo: ModeloSessao }) {
  const lista = Object.entries(modelo.estado.consentimentos ?? {});
  // Hora do pedido/decisão vem da auditoria da sessão, que registra cada mudança.
  const momento = (acao: string, tipo: TipoEventoAuditoria) =>
    modelo.auditoria.findLast((e) => e.tipo_evento === tipo && e.resumo.startsWith(`${acao} ·`))?.ts;
  return (
    <>
      {lista.length === 0 && <p className="tl-sub">Nenhum consentimento pedido ainda.</p>}
      {lista.map(([acao, c]) => {
        const st = ROTULO_STATUS[c.status];
        const pendente = c.status === "pendente";
        const ts = momento(acao, pendente ? "consentimento_solicitado" : "consentimento_decidido") ?? c.ts;
        return (
          <div key={`${acao}-${c.consent_id}`} className={pendente ? "p-card new" : "p-card"}>
            <div className="row-between">
              <span className="mono" style={{ fontWeight: 600 }}>
                {acao}
              </span>
              <span className={`badge ${st.classe}`} style={{ height: 24, fontSize: 12 }}>
                <Icone nome={pendente ? "alerta" : c.status === "aceito" ? "check" : "x"} tamanho="sm" />
                {st.texto}
              </span>
            </div>
            <span className="tl-sub">
              {pendente ? "solicitado" : "decidido"} {ts !== undefined ? horaSegundos(ts) : "—"} · id {mascararId(c.consent_id)}
            </span>
          </div>
        );
      })}
      <div className="p-card">
        <span className="eyebrow">Regra de governança</span>
        <span className="tl-sub">Ações sensíveis passam por solicitar_consentimento. Sem decisão, nada é executado.</span>
      </div>
    </>
  );
}

const PONTO_AUDITORIA: Partial<Record<TipoEventoAuditoria, string>> = {
  plano_criado: "ok",
  acao_executada: "ok",
  consentimento_decidido: "ok",
  plano_ajustado: "ok",
  consentimento_solicitado: "warn",
  desvio_detectado: "warn",
  guardrail_bloqueio: "err",
};

function AbaAuditoria({ auditoria }: { auditoria: EventoAuditoria[] }) {
  const recentes = [...auditoria].reverse();
  return (
    <ol style={{ listStyle: "none", margin: 0, padding: 0 }} aria-label="Eventos de auditoria, do mais recente">
      {recentes.map((e, i) => (
        <li key={`${e.ts}-${e.tipo_evento}-${recentes.length - i}`} className={i === recentes.length - 1 ? "tl-item last" : "tl-item"}>
          <span className={`tl-dot ${i === 0 ? "now" : (PONTO_AUDITORIA[e.tipo_evento] ?? "done")}`} aria-hidden="true" />
          <div className="tl-main">
            <div className="tl-title">
              <span className="mono" style={{ fontWeight: 600 }}>
                {e.tipo_evento}
              </span>
              <span className="mono" style={{ color: "var(--ink-3)" }}>
                {horaSegundos(e.ts)}
              </span>
            </div>
            <span className="tl-sub">
              {e.resumo}
              {e.estado_jornada ? ` · ${e.estado_jornada}` : ""}
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}

/** Rodapé com o state da sessão; o cliente aparece só mascarado (FR-018). */
export function RodapeEstado({ modelo }: { modelo: ModeloSessao }) {
  const { estado } = modelo;
  const o = estado.objetivo;
  const objetivo = o
    ? [o.descricao ?? o.tipo, typeof o.valor_alvo === "number" ? brl(o.valor_alvo) : null, typeof o.prazo_meses === "number" ? `${o.prazo_meses}m` : null]
        .filter(Boolean)
        .join(" · ")
    : "—";
  const cenario = estado.cenario_escolhido ? estado.cenario_escolhido.charAt(0).toUpperCase() + estado.cenario_escolhido.slice(1) : "—";
  const cliente = estado.id_usuario ? mascararId(estado.id_usuario) : CONFIG.idUsuarioMascarado;
  return (
    <dl className="kv" style={{ margin: 0 }}>
      <div>
        <dt className="k">Objetivo</dt>
        <dd className="v" style={{ margin: 0 }}>
          {objetivo}
        </dd>
      </div>
      <div>
        <dt className="k">Cenário</dt>
        <dd className="v" style={{ margin: 0 }}>
          {cenario}
        </dd>
      </div>
      <div>
        <dt className="k">Mês de ref.</dt>
        <dd className="v num" style={{ margin: 0 }}>
          {mesAbrev(estado.ate_anomes)}
        </dd>
      </div>
      <div>
        <dt className="k">Plano</dt>
        <dd className="v mono" style={{ margin: 0, fontSize: 13 }}>
          {estado.plano_id ? mascararId(estado.plano_id) : "—"}
        </dd>
      </div>
      <div>
        <dt className="k">Cliente</dt>
        <dd className="v mono" style={{ margin: 0, fontSize: 13 }}>
          {cliente}
        </dd>
      </div>
      <div>
        <dt className="k">Atualizado</dt>
        <dd className="v num" style={{ margin: 0 }}>
          {modelo.auditoria.length > 0 ? hora(modelo.auditoria[modelo.auditoria.length - 1].ts) : "—"}
        </dd>
      </div>
    </dl>
  );
}

interface Props {
  modelo: ModeloSessao;
  variante: "painel" | "folha";
  onFechar: () => void;
  /** Barra do apresentador (BarraDemo), dentro do painel no mobile. */
  apresentador: ReactNode;
}

export function Bastidores({ modelo, variante, onFechar, apresentador }: Props) {
  const [aba, setAba] = useState<Aba>("Jornada");
  const fechar = useRef<HTMLButtonElement>(null);
  const folha = variante === "folha";

  useEffect(() => {
    if (!folha) return;
    fechar.current?.focus();
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") onFechar();
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [folha, onFechar]);

  const cabecalho = (
    <div className="row-between" style={{ padding: folha ? "4px 12px 10px 18px" : "16px 16px 12px 18px", flexWrap: "nowrap" }}>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span className="eyebrow">Bastidores</span>
        <span style={{ fontSize: folha ? 17 : 16, fontWeight: 900 }}>O agente por dentro</span>
      </div>
      <button
        ref={fechar}
        type="button"
        className="icon-btn"
        aria-label={folha ? "Fechar Bastidores" : "Recolher Bastidores"}
        onClick={onFechar}
        style={folha ? { border: 0 } : undefined}
      >
        <Icone nome={folha ? "x" : "chevronDireita"} />
      </button>
    </div>
  );

  const corpo = (
    <>
      <nav className="tabs" aria-label="Seções dos Bastidores">
        {ABAS.map((a) => (
          <button
            key={a}
            type="button"
            className={a === aba ? "tab on" : "tab"}
            aria-current={a === aba ? "true" : undefined}
            aria-label={folha && ABAS_CURTAS[a] !== a ? a : undefined}
            onClick={() => setAba(a)}
          >
            {folha ? ABAS_CURTAS[a] : a}
          </button>
        ))}
      </nav>
      <div className="panel-body" aria-live="polite">
        {aba === "Jornada" && <AbaJornada modelo={modelo} />}
        {aba === "Ferramentas" && <AbaFerramentas modelo={modelo} />}
        {aba === "Consentimentos" && <AbaConsentimentos modelo={modelo} />}
        {aba === "Auditoria" && <AbaAuditoria auditoria={modelo.auditoria} />}
      </div>
      <RodapeEstado modelo={modelo} />
    </>
  );

  if (folha) {
    return (
      <>
        <div className="sheet-backdrop" aria-hidden="true" onClick={onFechar} />
        <section className="sheet" role="dialog" aria-modal="true" aria-label="Bastidores">
          <span className="grip" aria-hidden="true" />
          {cabecalho}
          <div style={{ margin: "0 14px 12px" }}>{apresentador}</div>
          {corpo}
        </section>
      </>
    );
  }

  return (
    <aside aria-label="Bastidores" style={{ width: 360, flexShrink: 0, display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
      {apresentador}
      <section className="glass-chrome panel" style={{ flexGrow: 1, minHeight: 0 }}>
        {cabecalho}
        {corpo}
      </section>
    </aside>
  );
}
