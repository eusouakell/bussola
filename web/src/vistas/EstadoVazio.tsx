// Sem plano criado: as vistas não inventam dados e levam de volta à conversa.
import { Icone } from "../componentes/base/Icone";
import { BotaoAcao } from "./partes";

interface Props {
  onConversa: () => void;
}

export function EstadoVazio({ onConversa }: Props) {
  return (
    <section aria-label="EstadoVazio" className="glass-card card-pad enter" style={{ alignItems: "center", textAlign: "center" }}>
      <span className="brand-mark" aria-hidden="true" style={{ width: 48, height: 48, borderRadius: 16 }}>
        <Icone nome="alvo" />
      </span>
      <span className="t-title" style={{ fontSize: 20 }}>
        Você ainda não tem um plano
      </span>
      <p className="prose" style={{ margin: 0, color: "var(--ink-2)" }}>
        O plano nasce na conversa: conte seu objetivo, compare os caminhos e autorize a criação. Depois ele aparece aqui, com
        a fonte de cada número.
      </p>
      <BotaoAcao primario icone="conversa" onClick={onConversa}>
        Voltar para a conversa
      </BotaoAcao>
    </section>
  );
}
