import type { TagMensagem } from "../../agente/tipos";
import { Icone, type NomeIcone } from "./Icone";

const TAGS: Record<TagMensagem, { classe: string; icone: NomeIcone; rotulo: string }> = {
  diagnostico: { classe: "tag-diag", icone: "diag", rotulo: "Diagnóstico" },
  simulacao: { classe: "tag-sim", icone: "sim", rotulo: "Simulação" },
  recomendacao: { classe: "tag-rec", icone: "rec", rotulo: "Recomendação" },
  acao: { classe: "tag-acao", icone: "escudo", rotulo: "Ação" },
};

interface Props {
  tipo: TagMensagem;
  /** Texto no lugar do rótulo padrão ("Plano criado", "Ação · requer sua autorização"). */
  texto?: string;
}

export function Tag({ tipo, texto }: Props) {
  const t = TAGS[tipo];
  return (
    <span className={`tag ${t.classe}`}>
      <Icone nome={t.icone} tamanho="sm" traco={2.4} />
      {texto ?? t.rotulo}
    </span>
  );
}
