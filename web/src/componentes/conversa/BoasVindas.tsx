// Entrada da jornada — uma escolha principal, sem manual de uso na primeira dobra.
import { SUGESTOES_INICIAIS } from "../../sessao/sugestoes-padrao";
import { Icone, type NomeIcone } from "../base/Icone";

const OBJETIVOS: { rotulo: string; icone: NomeIcone }[] = [
  { rotulo: "Comprar um apartamento", icone: "casa" },
  { rotulo: "Planejar uma viagem", icone: "aviao" },
  { rotulo: "Fazer uma pós", icone: "capelo" },
  { rotulo: "Organizar dívidas", icone: "lista" },
];

interface Props {
  nome?: string;
  onEscolher: (texto: string) => void;
  desabilitado: boolean;
  compacto?: boolean;
}

export function BoasVindas({ nome = "Fernando", onEscolher, desabilitado, compacto }: Props) {
  return (
    <section className="welcome-simple enter" aria-label="Iniciar planejamento financeiro">
      <span className="welcome-eyebrow">Oi, {nome}.</span>
      <h1>O que você quer realizar?</h1>
      <p className="welcome-intro">Comece pelo seu objetivo. A Bússola ajuda a explorar possibilidades.</p>
      <div role="group" aria-label="Escolha um objetivo" className={compacto ? "welcome-options compact" : "welcome-options"}>
        {SUGESTOES_INICIAIS.map((texto, i) => {
          const objetivo = OBJETIVOS[i];
          return (
            <button
              type="button"
              key={texto}
              className="welcome-option"
              disabled={desabilitado}
              onClick={() => onEscolher(texto)}
              aria-label={objetivo?.rotulo ?? texto}
            >
              <Icone nome={objetivo?.icone ?? "alvo"} tamanho="lg" />
              <span>{objetivo?.rotulo ?? texto}</span>
              <span className="welcome-arrow" aria-hidden="true">↗</span>
            </button>
          );
        })}
      </div>
      <p className="welcome-legal">
        {compacto ? "Simulação. Você decide." : "Os valores são simulados. Nenhuma ação sensível ocorre sem sua autorização."}
      </p>
    </section>
  );
}
