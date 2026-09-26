// Erro de ferramenta na conversa (contracts/eventos-agente.md §4): copy fixa
// por código; `erro.mensagem` nunca aparece.
import { mensagemErro, mensagemTentarDeNovo, podeTentarDeNovo } from "../../sessao/catalogo";
import { Icone } from "../base/Icone";

/** Códigos que a conversa não mostra aqui (§4.1). */
export function erroVisivelNaConversa(nome: string, codigo: string): boolean {
  if (codigo === "CONSENTIMENTO_NECESSARIO") return false;
  if (codigo === "DADOS_INSUFICIENTES" && (nome === "perfil_financeiro" || nome === "capacidade_poupanca")) return false;
  return true;
}

interface Props {
  nome: string;
  codigo: string;
  onEnviar?: (texto: string) => void;
  desabilitado?: boolean;
}

export function ErroFerramenta({ nome, codigo, onEnviar, desabilitado }: Props) {
  if (!erroVisivelNaConversa(nome, codigo)) return null;
  const mensagem = mensagemErro(codigo, nome);
  if (!podeTentarDeNovo(codigo)) {
    return (
      <div className="note note-warn" role="note" style={{ fontSize: 14.5, lineHeight: "20px", padding: "10px 12px" }}>
        <Icone nome="alerta" />
        <span>{mensagem}</span>
      </div>
    );
  }
  return (
    <div className="tool-erro" role="alert" aria-label="ErroFerramenta">
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span className="st st-err">
          <Icone nome="x" tamanho="sm" traco={3} />
        </span>
        <span style={{ fontSize: 14.5, fontWeight: 800, color: "var(--err)" }}>{mensagem}</span>
      </div>
      {onEnviar && (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ alignSelf: "flex-start", marginLeft: 34 }}
          disabled={desabilitado}
          onClick={() => onEnviar(mensagemTentarDeNovo(nome))}
        >
          <Icone nome="recarregar" />
          Tentar de novo
        </button>
      )}
    </div>
  );
}
