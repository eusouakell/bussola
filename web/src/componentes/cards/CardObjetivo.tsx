// Objetivo registrado (etapa OBJETIVO): o que já está definido e o que falta.
import { dadosDe } from "../../agente/envelope";
import { brl, meses } from "../../formatacao/formatar";
import type { ItemCard } from "../../sessao/modelo";
import { Icone } from "../base/Icone";
import { capitalizar, num, obj, textos, txt } from "./ler";

const TIPOS: Record<string, string> = {
  imovel: "Imóvel",
  viagem: "Viagem",
  educacao: "Educação",
  dividas: "Quitar dívidas",
};

interface Linha {
  chave: string;
  rotulo: string;
  valor: string | undefined;
}

export function CardObjetivo({ item }: { item: ItemCard }) {
  const dados = dadosDe(item.resposta);
  const objetivo = obj(dados, "objetivo");
  const faltando = new Set(textos(dados, "faltando"));
  const tipo = txt(objetivo, "tipo");
  const valor = num(objetivo, "valor_alvo");
  const prazo = num(objetivo, "prazo_meses");
  const linhas: Linha[] = [
    { chave: "tipo", rotulo: "Tipo", valor: tipo ? (TIPOS[tipo] ?? capitalizar(tipo)) : undefined },
    { chave: "valor_alvo", rotulo: "Quanto juntar", valor: valor !== undefined ? brl(valor) : undefined },
    { chave: "prazo_meses", rotulo: "Em quanto tempo", valor: prazo !== undefined ? meses(prazo) : undefined },
    { chave: "prioridade", rotulo: "Prioridade", valor: capitalizar(txt(objetivo, "prioridade")) },
  ];
  return (
    <article className="glass-card card-pad enter" aria-label="CardObjetivo">
      <div className="row-between">
        <span className="eyebrow">Seu objetivo</span>
        <Icone nome="alvo" estilo={{ color: "var(--accent)" }} />
      </div>
      <span className="t-title">{txt(objetivo, "descricao") ?? "Objetivo"}</span>
      <div className="grid-2">
        {linhas.map((l) => {
          const falta = faltando.has(l.chave) || l.valor === undefined || l.valor === "—";
          return (
            <div key={l.chave} className={falta ? "check-item falta" : "check-item"} style={{ alignItems: "center" }}>
              {falta ? (
                <span className="st st-q" role="img" aria-label="Falta definir">
                  <Icone nome="alerta" tamanho="sm" />
                </span>
              ) : (
                <span className="st st-ok" role="img" aria-label="Definido">
                  <Icone nome="check" tamanho="sm" traco={3} />
                </span>
              )}
              <span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                <span className="small" style={{ fontWeight: 700 }}>
                  {l.rotulo}
                </span>
                <span className="num" style={{ fontSize: 16, fontWeight: 800, color: falta ? "var(--warn)" : undefined }}>
                  {falta ? "Falta definir" : l.valor}
                </span>
              </span>
            </div>
          );
        })}
      </div>
    </article>
  );
}
