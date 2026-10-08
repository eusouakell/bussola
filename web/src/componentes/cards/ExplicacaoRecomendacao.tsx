// Fontes opcionais da orientação. Sem cartão redundante na conversa.
import { avisosDe, dadosDe } from "../../agente/envelope";
import type { ItemCard } from "../../sessao/modelo";
import { lista, obj, txt } from "./ler";

/** Metadados da demonstração e aviso educativo padrão já aparecem no contexto geral.
 *  Alertas materiais (ex.: fonte não localizada) continuam visíveis. */
export function avisosContextuais(avisos: string[]): string[] {
  return [...new Set(avisos)].filter((aviso) =>
    !/^Resposta simulada pelo front; regravar após o ciclo \d{3}$/.test(aviso) &&
    !/conteúdo educativo e geral, não é recomendação individual/i.test(aviso) &&
    !/confira a norma em vigor no site do Banco Central/i.test(aviso) &&
    !/\bmock\b|valor_alvo\s*=|prazo_meses\s*=/i.test(aviso),
  );
}

export function ExplicacaoRecomendacao({ item }: { item: ItemCard }) {
  const trechos = lista(dadosDe(item.resposta), "trechos");
  const alertas = avisosContextuais(avisosDe(item.resposta));
  if (trechos.length === 0 && alertas.length === 0) return null;

  return (
    <div className="fonte-orientacao" aria-label="Informações complementares da orientação">
      {alertas.map((aviso) => (
        <p key={aviso} className="fonte-aviso" role="status">{aviso}</p>
      ))}
      {trechos.length > 0 && (
        <details className="fonte-detalhes">
          <summary>Fontes consultadas</summary>
          <ul>
            {trechos.map((trecho, indice) => {
              const fonte = obj(trecho, "fonte");
              const identificador = txt(trecho, "trecho_id") ?? String(indice);
              return (
                <li key={identificador}>
                  <strong>{txt(trecho, "titulo") ?? "Referência"}</strong>
                  {fonte && (
                    <span className="fonte-origem">
                      {[txt(fonte, "nome"), txt(fonte, "referencia")].filter(Boolean).join(" · ")}
                    </span>
                  )}
                  {txt(trecho, "texto") && <p>{txt(trecho, "texto")}</p>}
                </li>
              );
            })}
          </ul>
          <p className="fonte-ressalva">Fontes informam a explicação; os valores da simulação são calculados separadamente.</p>
        </details>
      )}
    </div>
  );
}
