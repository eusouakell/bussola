// Falha de conexão com o agente ao vivo (FR-020): nunca tela em branco.
import type { ItemFalhaConexao } from "../../sessao/modelo";
import { Icone } from "../base/Icone";

interface Props {
  item: ItemFalhaConexao;
  /** Reenvia a mensagem que falhou ou, sem ela, recomeça a sessão. */
  onTentar: () => void;
  onModoSimulado?: () => void;
  ocupado: boolean;
}

export function FalhaConexao({ item, onTentar, onModoSimulado, ocupado }: Props) {
  return (
    <article className="glass-card enter card-pad" role="alert" aria-label="Falha de conexão" style={{ gap: 12 }}>
      <div className="note note-err">
        <Icone nome="alerta" />
        <span>{item.mensagem}</span>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-secondary btn-sm" disabled={ocupado} onClick={onTentar}>
          <Icone nome="recarregar" />
          Tentar de novo
        </button>
        {onModoSimulado && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={onModoSimulado}>
            <Icone nome="frasco" />
            Usar modo simulado
          </button>
        )}
      </div>
    </article>
  );
}
