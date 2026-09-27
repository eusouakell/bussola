// Chamadas de ferramenta de um trecho do turno (FR-006): linha por ferramenta
// com estado; várias chamadas viram "Analisando sua situação · k de N".
import { useState } from "react";
import { fonteDe } from "../../agente/envelope";
import { periodo } from "../../formatacao/formatar";
import { mensagemErro, nomeLegivel } from "../../sessao/catalogo";
import type { ItemFerramenta } from "../../sessao/modelo";
import { Icone } from "../base/Icone";
import { ErroFerramenta, erroVisivelNaConversa } from "./ErroFerramenta";

function codigoErro(item: ItemFerramenta): string | undefined {
  return item.resposta?.tipo === "erro" ? item.resposta.codigo : undefined;
}

/**
 * Erros visíveis agrupados por mensagem (BUG-05b): várias ferramentas com a
 * mesma copy viram um aviso só. Quais falharam continua nas linhas da lista.
 */
function errosPorMensagem(itens: ItemFerramenta[]): { chave: string; nome: string; codigo: string }[] {
  const porMensagem = new Map<string, { chave: string; nome: string; codigo: string }>();
  for (const item of itens) {
    const codigo = codigoErro(item);
    if (codigo === undefined || !erroVisivelNaConversa(item.nome, codigo)) continue;
    const mensagem = mensagemErro(codigo, item.nome);
    if (!porMensagem.has(mensagem)) porMensagem.set(mensagem, { chave: item.chave, nome: item.nome, codigo });
  }
  return [...porMensagem.values()];
}

function Status({ item }: { item: ItemFerramenta }) {
  if (item.status === "consultando") return <span className="spin" role="status" aria-label="Consultando" />;
  const codigo = codigoErro(item);
  if (codigo && erroVisivelNaConversa(item.nome, codigo)) {
    return (
      <span className="st st-err" role="img" aria-label="Falhou">
        <Icone nome="x" tamanho="sm" traco={3} />
      </span>
    );
  }
  if (codigo) {
    return (
      <span className="st st-q" role="img" aria-label="Com ressalva">
        <Icone nome="alerta" tamanho="sm" />
      </span>
    );
  }
  return (
    <span className="st st-ok" role="img" aria-label="Concluída">
      <Icone nome="check" tamanho="sm" traco={3} />
    </span>
  );
}

export function LinhaFerramenta({ item }: { item: ItemFerramenta }) {
  const fonte = fonteDe(item.resposta);
  return (
    <div className="tool-line">
      <Status item={item} />
      <span className="nm">{nomeLegivel(item.nome)}</span>
      {fonte?.periodo && <span className="per num">{periodo(fonte.periodo)}</span>}
    </div>
  );
}

interface Props {
  itens: ItemFerramenta[];
  onEnviar: (texto: string) => void;
  ocupado: boolean;
}

export function BlocoAnalise({ itens, onEnviar, ocupado }: Props) {
  const [escolha, setEscolha] = useState<boolean | null>(null);
  const emAndamento = itens.some((i) => i.status === "consultando");
  const concluidas = itens.filter((i) => i.status !== "consultando").length;
  const erros = errosPorMensagem(itens);

  if (itens.length === 1) {
    const [item] = itens;
    const codigo = codigoErro(item);
    return (
      <div className="glass-card tool-block" aria-live="polite" aria-label={nomeLegivel(item.nome)}>
        <LinhaFerramenta item={item} />
        {codigo && <ErroFerramenta nome={item.nome} codigo={codigo} onEnviar={onEnviar} desabilitado={ocupado} />}
      </div>
    );
  }

  const aberto = escolha ?? emAndamento;
  const periodoComum = itens.map((i) => fonteDe(i.resposta)?.periodo).find(Boolean);
  return (
    <div className="glass-card tool-block" aria-live="polite" aria-label={emAndamento ? "Analisando sua situação" : "Análise concluída"}>
      <button type="button" className="tool-head" aria-expanded={aberto} onClick={() => setEscolha(!aberto)}>
        {emAndamento ? (
          <span className="spin" aria-hidden="true" />
        ) : erros.length > 0 ? (
          <span className="st st-q">
            <Icone nome="alerta" tamanho="sm" />
          </span>
        ) : (
          <span className="st st-ok">
            <Icone nome="check" tamanho="sm" traco={3} />
          </span>
        )}
        <span style={{ flex: "1 1 auto" }}>
          {emAndamento ? "Analisando sua situação" : "Analisei sua situação"}{" "}
          <span className="num" style={{ fontWeight: 600, color: "var(--ink-3)" }}>
            {emAndamento
              ? `· ${concluidas} de ${itens.length}`
              : `· ${itens.length} consultas${periodoComum ? ` · ${periodo(periodoComum)}` : ""}`}
          </span>
        </span>
        <Icone nome="chevronBaixo" estilo={{ transform: aberto ? "rotate(180deg)" : undefined, color: "var(--ink-3)" }} />
      </button>
      {aberto && itens.map((item) => <LinhaFerramenta key={item.chave} item={item} />)}
      {erros.map((erro) => (
        <ErroFerramenta key={`${erro.chave}-erro`} nome={erro.nome} codigo={erro.codigo} onEnviar={onEnviar} desabilitado={ocupado} />
      ))}
    </div>
  );
}
