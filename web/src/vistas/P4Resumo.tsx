// P4 · Resumo do plano: caminho escolhido, premissas da simulação, fontes
// usadas e autorizações do `session.state`. Só leitura (FR-024).
import { dadosDe, fonteDe } from "../agente/envelope";
import type { Consentimento } from "../agente/tipos";
import { Disclaimer, DISCLAIMER_SIMULACAO } from "../componentes/base/Disclaimer";
import { Icone, type NomeIcone } from "../componentes/base/Icone";
import { bool, capitalizar, num, obj, textos, txt } from "../componentes/cards/ler";
import { brl, dataHora, fracaoPercentual, mascararId, meses, periodo } from "../formatacao/formatar";
import { nomeLegivel } from "../sessao/catalogo";
import { cenarioComparado, fontesUsadas, type PlanoLido } from "./dados";
import { Fonte } from "./partes";

interface Props {
  plano: PlanoLido;
}

export function P4Resumo({ plano }: Props) {
  return (
    <section aria-label="P4Resumo" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <article className="glass-card enter" aria-label="Resumo do plano" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="row-between">
          <span className="eyebrow">Caminho escolhido</span>
          <span className="mono small" style={{ color: "var(--ink-3)" }}>
            plano {mascararId(plano.planoId)}
          </span>
        </div>
        <Caminho plano={plano} />
        <div className="hline" />
        <span className="eyebrow">Premissas</span>
        <Premissas plano={plano} />
        <div className="hline" />
        <span className="eyebrow">Fontes usadas</span>
        <FontesUsadas plano={plano} />
      </article>

      <Autorizacoes consentimentos={plano.consentimentos} />

      <Disclaimer centralizado>{DISCLAIMER_SIMULACAO}</Disclaimer>
    </section>
  );
}

function Caminho({ plano }: { plano: PlanoLido }) {
  const criacao = dadosDe(plano.criacao?.resposta);
  const ajuste = dadosDe(plano.ajuste?.resposta);
  const comparado = cenarioComparado(plano);
  const pct = num(comparado, "pct_capacidade");
  const tradeOffs = textos(comparado, "trade_offs").slice(0, 2);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div className="row-between">
        <span style={{ fontSize: 18, fontWeight: 900 }}>{capitalizar(plano.cenario)}</span>
        {plano.criacao && (
          <span className="small num" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontWeight: 800, color: "var(--ink)" }}>
            {brl(num(criacao, "aporte_mensal"))}/mês · {meses(num(criacao, "prazo_meses"))}
            <Fonte origem={plano.criacao} compacto />
          </span>
        )}
      </div>
      {comparado && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {pct !== undefined && (
            <span className="small">
              Usa <strong className="num">{fracaoPercentual(pct)}</strong> da sua sobra mensal mediana.
            </span>
          )}
          {tradeOffs.map((t) => (
            <span key={t} className="small">
              {t}
            </span>
          ))}
          <Fonte origem={plano.comparacao} />
        </div>
      )}
      {plano.ajuste && (
        <div className="note note-info" style={{ fontSize: 14, lineHeight: "19px", padding: "9px 12px", alignItems: "center" }}>
          <Icone nome="recarregar" />
          <span className="num" style={{ flex: "1 1 auto" }}>
            Ajustado{txt(ajuste, "rota") ? ` pela rota ${txt(ajuste, "rota")}` : ""}: {brl(num(ajuste, "aporte_mensal"))}/mês,{" "}
            {meses(num(ajuste, "prazo_meses"))} no total.
          </span>
          <Fonte origem={plano.ajuste} compacto />
        </div>
      )}
    </div>
  );
}

function Premissas({ plano }: { plano: PlanoLido }) {
  const dados = dadosDe(plano.simulacao?.resposta);
  const p = obj(dados, "premissas");
  if (!p) return <p className="small" style={{ margin: 0 }}>As premissas aparecem depois da simulação do objetivo na conversa.</p>;
  const rendimento = num(p, "rendimento_mensal");
  const usarSaldo = bool(p, "usar_saldo_atual");
  const capacidade = num(p, "capacidade_mensal");
  const base = txt(p, "base_capacidade");
  const mesesBase = num(p, "meses_considerados");
  const itens: string[] = [];
  if (rendimento !== undefined) itens.push(rendimento === 0 ? "Sem rendimento considerado" : `Rendimento de ${fracaoPercentual(rendimento)} ao mês`);
  if (usarSaldo !== undefined) {
    itens.push(usarSaldo ? `Usa o saldo atual da conta (${brl(num(p, "saldo_inicial"))})` : "Sem usar o saldo atual da conta");
  }
  if (capacidade !== undefined) {
    itens.push(`Capacidade de ${brl(capacidade)}/mês${base === "sobra_mediana" ? " (sobra mediana)" : ""}`);
  }
  const periodoBase = fonteDe(plano.simulacao?.resposta)?.periodo;
  if (mesesBase !== undefined) itens.push(`Base de ${meses(mesesBase)}${periodoBase ? ` · ${periodo(periodoBase)}` : ""}`);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-start" }}>
      <ul className="small num" style={{ margin: 0, paddingLeft: 18 }}>
        {itens.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
      <Fonte origem={plano.simulacao} />
    </div>
  );
}

function FontesUsadas({ plano }: { plano: PlanoLido }) {
  const fontes = fontesUsadas(plano.todas);
  if (fontes.length === 0) return <p className="small" style={{ margin: 0 }}>Nenhuma consulta com fonte nesta sessão.</p>;
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {fontes.map((r) => (
        <Fonte key={r.nome} origem={r} rotulo={nomeLegivel(r.nome)} />
      ))}
    </div>
  );
}

const ACOES: Record<string, string> = {
  criar_plano: "Criar e acompanhar o plano",
  ativar_lembretes: "Lembretes mensais",
  ajustar_plano: "Ajustar o plano",
  simular_contratacao: "Simulação de financiamento",
};

const STATUS: Record<Consentimento["status"], { rotulo: string; classe: string; icone: NomeIcone }> = {
  aceito: { rotulo: "Autorizado", classe: "badge badge-ok", icone: "check" },
  recusado: { rotulo: "Não autorizado", classe: "badge badge-neutral", icone: "x" },
  pendente: { rotulo: "Aguardando resposta", classe: "badge badge-warn", icone: "alerta" },
};

function Autorizacoes({ consentimentos }: { consentimentos: Record<string, Consentimento> }) {
  const lista = Object.entries(consentimentos);
  return (
    <article className="glass-consent enter" aria-label="Suas autorizações" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Icone nome="escudo" />
        <span style={{ fontSize: 17, fontWeight: 900 }}>Suas autorizações</span>
      </div>
      {lista.length === 0 && <p className="small" style={{ margin: 0 }}>Nenhuma autorização registrada nesta sessão.</p>}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        {lista.map(([acao, c]) => {
          const s = STATUS[c.status] ?? STATUS.pendente;
          return (
            <li key={acao} className="check-item" style={{ padding: "10px 12px", alignItems: "center", flexWrap: "wrap" }}>
              <div style={{ display: "flex", flexDirection: "column", flex: "1 1 auto", minWidth: 0 }}>
                <span style={{ fontSize: 14.5, fontWeight: 800 }}>{ACOES[acao] ?? c.resumo ?? nomeLegivel(acao)}</span>
                <span className="small num" style={{ fontSize: 12.5 }}>
                  {c.ts !== undefined && <>{dataHora(c.ts)} · </>}
                  <span className="mono">{mascararId(c.consent_id)}</span>
                </span>
              </div>
              <span className={s.classe} style={{ height: 24, fontSize: 12 }}>
                <Icone nome={s.icone} tamanho="sm" />
                {s.rotulo}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="small" style={{ margin: 0, fontSize: 13.5 }}>
        Nenhuma autorização move dinheiro, contrata produtos ou compartilha seus dados.
      </p>
    </article>
  );
}
