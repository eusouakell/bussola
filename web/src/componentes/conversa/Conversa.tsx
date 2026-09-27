// Linha do tempo da conversa: agrupa os itens do modelo em mensagens do
// cliente, divisores de mês e blocos do agente (marca + corpo), e escolhe o
// card de cada resposta de ferramenta (catálogo em sessao/catalogo.ts).
import { useEffect, useRef, type ReactNode } from "react";
import type { EstadoSessao } from "../../agente/tipos";
import type { ItemCard, ItemConversa, ItemFerramenta } from "../../sessao/modelo";
import { Icone } from "../base/Icone";
import { CardConsentimento } from "../cards/CardConsentimento";
import { CardDiagnostico } from "../cards/CardDiagnostico";
import { CardDividas } from "../cards/CardDividas";
import { CardMarcos } from "../cards/CardMarcos";
import { CardObjetivo } from "../cards/CardObjetivo";
import { CardOportunidadesCorte } from "../cards/CardOportunidadesCorte";
import { CardPlano } from "../cards/CardPlano";
import { CardSimulacao } from "../cards/CardSimulacao";
import { ComparadorCenarios } from "../cards/ComparadorCenarios";
import { ExplicacaoRecomendacao } from "../cards/ExplicacaoRecomendacao";
import {
  CardOportunidade,
  CardPlanejadoRealizado,
  CardRotaRecalculada,
  CardStatusPlano,
  DivisorMes,
  ReciboAcao,
} from "../cards/acompanhar";
import { AlertaGuardrail } from "./AlertaGuardrail";
import { BlocoAnalise } from "./BlocoAnalise";
import { FalhaConexao } from "./FalhaConexao";
import { MensagemAgente } from "./MensagemAgente";
import { MensagemCliente } from "./MensagemCliente";
import { Skeleton } from "./Skeleton";

type Parte = { tipo: "ferramentas"; chave: string; itens: ItemFerramenta[] } | { tipo: "item"; item: ItemConversa };

type Grupo =
  | { tipo: "fora"; item: ItemConversa }
  | { tipo: "agente"; chave: string; partes: Parte[] };

/** Cliente e divisores ficam fora do bloco do agente; ferramentas seguidas viram um BlocoAnalise. */
export function agrupar(itens: ItemConversa[]): Grupo[] {
  const grupos: Grupo[] = [];
  for (const item of itens) {
    if (item.tipo === "mensagem_cliente" || item.tipo === "divisor_mes") {
      grupos.push({ tipo: "fora", item });
      continue;
    }
    let grupo = grupos.at(-1);
    if (grupo?.tipo !== "agente") {
      grupo = { tipo: "agente", chave: item.chave, partes: [] };
      grupos.push(grupo);
    }
    const ultima = grupo.partes.at(-1);
    if (item.tipo === "ferramenta") {
      if (ultima?.tipo === "ferramentas") ultima.itens.push(item);
      else grupo.partes.push({ tipo: "ferramentas", chave: item.chave, itens: [item] });
    } else {
      grupo.partes.push({ tipo: "item", item });
    }
  }
  return grupos;
}

interface Props {
  itens: ItemConversa[];
  estado: EstadoSessao;
  ocupado: boolean;
  /** E5: skeleton enquanto uma consulta do turno roda. */
  lento: boolean;
  onEnviar: (texto: string) => void;
  /** "Tentar de novo" de uma falha de conexão. */
  onRepetir: () => void;
  onModoSimulado?: () => void;
  /** Conteúdo antes da conversa começar (boas-vindas). */
  vazio?: ReactNode;
}

export function Conversa({ itens, estado, ocupado, lento, onEnviar, onRepetir, onModoSimulado, vazio }: Props) {
  const rolagem = useRef<HTMLElement>(null);
  const grupos = agrupar(itens);
  const ultimo = itens.at(-1);
  const semCliente = !itens.some((i) => i.tipo === "mensagem_cliente");
  const consultando = itens.some((i) => i.tipo === "ferramenta" && i.status === "consultando");
  const esperando = ocupado && (ultimo?.tipo === "mensagem_cliente" || ultimo?.tipo === "divisor_mes");

  // Rola para o fim a cada novidade; nas boas-vindas fica no topo.
  useEffect(() => {
    const el = rolagem.current;
    if (el) el.scrollTop = semCliente ? 0 : el.scrollHeight;
  }, [itens, ocupado, semCliente]);

  function card(item: ItemCard): ReactNode {
    switch (item.componente) {
      case "CardDiagnostico":
        return <CardDiagnostico item={item} />;
      case "CardDividas":
        return <CardDividas item={item} />;
      case "CardOportunidadesCorte":
        return <CardOportunidadesCorte item={item} />;
      case "CardSimulacao":
        return <CardSimulacao item={item} />;
      case "ComparadorCenarios":
        return <ComparadorCenarios item={item} onEnviar={onEnviar} ocupado={ocupado} cenarioEscolhido={estado.cenario_escolhido} />;
      case "CardMarcos":
        return <CardMarcos item={item} />;
      case "ExplicacaoRecomendacao":
        return <ExplicacaoRecomendacao item={item} />;
      case "CardObjetivo":
        return <CardObjetivo item={item} />;
      case "CardPlano":
        return <CardPlano item={item} consentimentos={estado.consentimentos} onEnviar={onEnviar} ocupado={ocupado} />;
      case "ReciboAcao":
        return <ReciboAcao item={item} />;
      case "CardPlanejadoRealizado":
        return <CardPlanejadoRealizado item={item} />;
      case "CardRotaRecalculada":
        return <CardRotaRecalculada item={item} onEnviar={onEnviar} ocupado={ocupado} />;
      case "CardOportunidade":
        return <CardOportunidade item={item} onEnviar={onEnviar} ocupado={ocupado} />;
      case "CardStatusPlano":
        return <CardStatusPlano item={item} />;
      default:
        return null;
    }
  }

  function parte(p: Parte): ReactNode {
    if (p.tipo === "ferramentas") return <BlocoAnalise key={p.chave} itens={p.itens} onEnviar={onEnviar} ocupado={ocupado} />;
    const item = p.item;
    switch (item.tipo) {
      case "mensagem_agente":
        return <MensagemAgente key={item.chave} item={item} />;
      case "card":
        return <div key={item.chave}>{card(item)}</div>;
      case "consentimento":
        return (
          <CardConsentimento
            key={item.chave}
            item={item}
            consentimento={estado.consentimentos?.[item.acao]}
            onEnviar={onEnviar}
            ocupado={ocupado}
          />
        );
      case "guardrail":
        return <AlertaGuardrail key={item.chave} item={item} ativo={item === ultimo} onEnviar={onEnviar} ocupado={ocupado} />;
      case "falha_conexao":
        return <FalhaConexao key={item.chave} item={item} onTentar={onRepetir} onModoSimulado={onModoSimulado} ocupado={ocupado} />;
      default:
        return null;
    }
  }

  const espera = esperando ? (
    <span className="typing" role="status" aria-label="A Bússola está respondendo">
      <span />
      <span />
      <span />
    </span>
  ) : null;
  const esqueleto = ocupado && lento && consultando ? <Skeleton /> : null;
  const ultimoGrupo = grupos.at(-1);
  const extraNoFim = ultimoGrupo?.tipo === "agente" ? esqueleto : null;
  const blocoNovo = (espera || (esqueleto && !extraNoFim)) && ultimoGrupo?.tipo !== "agente";

  return (
    <section ref={rolagem} className="convo" aria-label="Conversa" aria-live="polite" aria-busy={ocupado}>
      <div className="col" style={semCliente ? { marginBottom: "auto" } : undefined}>
        {semCliente && vazio}
        {grupos.map((g) =>
          g.tipo === "fora" ? (
            g.item.tipo === "mensagem_cliente" ? (
              <MensagemCliente key={g.item.chave} texto={g.item.texto} />
            ) : g.item.tipo === "divisor_mes" ? (
              <DivisorMes key={g.item.chave} item={g.item} />
            ) : null
          ) : (
            <BlocoAgente key={g.chave}>
              {g.partes.map(parte)}
              {g === ultimoGrupo && extraNoFim}
            </BlocoAgente>
          ),
        )}
        {blocoNovo && (
          <BlocoAgente>
            {espera}
            {esqueleto}
          </BlocoAgente>
        )}
      </div>
    </section>
  );
}

function BlocoAgente({ children }: { children: ReactNode }) {
  return (
    <div className="agent">
      <span className="brand-mark sm" aria-hidden="true">
        <Icone nome="bussola" tamanho="sm" />
      </span>
      <div className="agent-body">{children}</div>
    </div>
  );
}
