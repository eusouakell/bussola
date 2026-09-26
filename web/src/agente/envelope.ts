import type { Dados, Envelope, Fonte, RespostaFerramenta } from "./tipos";

/** `dados` do envelope ou do dado cru; erro vira objeto vazio. */
export function dadosDe(resposta: RespostaFerramenta | undefined): Dados {
  if (!resposta) return {};
  if (resposta.tipo === "envelope") return resposta.envelope.dados;
  if (resposta.tipo === "cru") return resposta.dados;
  return {};
}

export function fonteDe(resposta: RespostaFerramenta | undefined): Fonte | undefined {
  return resposta?.tipo === "envelope" ? resposta.envelope.fonte : undefined;
}

export function avisosDe(resposta: RespostaFerramenta | undefined): string[] {
  return resposta?.tipo === "envelope" ? resposta.envelope.avisos : [];
}

function ehObjeto(valor: unknown): valor is Dados {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function ehEnvelope(valor: unknown): valor is Envelope {
  return ehObjeto(valor) && "dados" in valor && ehObjeto(valor.fonte) && Array.isArray(valor.avisos);
}

function ehErro(valor: unknown): valor is { erro: { codigo: string } } {
  return ehObjeto(valor) && ehObjeto(valor.erro) && typeof valor.erro.codigo === "string";
}

function candidato(valor: unknown): unknown {
  if (!ehObjeto(valor)) return valor;
  if (ehEnvelope(valor) || ehErro(valor)) return valor;
  if ("result" in valor) return candidato(valor.result);
  if ("structuredContent" in valor && valor.structuredContent != null) {
    return candidato(valor.structuredContent);
  }
  if (Array.isArray(valor.content)) {
    for (const parte of valor.content) {
      if (ehObjeto(parte) && parte.type === "text" && typeof parte.text === "string") {
        try {
          const lido = candidato(JSON.parse(parte.text));
          if (ehEnvelope(lido) || ehErro(lido)) return lido;
        } catch {
          // texto que não é JSON: segue para o próximo pedaço
        }
      }
    }
  }
  return valor;
}

/**
 * Espelha `mcp_conexao._extrair_envelope` do agente (R4): envelope direto,
 * `{result}`, `{structuredContent}`, `{structuredContent: {result}}` e
 * `{content: [{type: "text", text: json}]}`. O resto é dado cru.
 */
export function extrairEnvelope(resposta: unknown): RespostaFerramenta {
  const valor = candidato(resposta);
  if (ehErro(valor)) return { tipo: "erro", codigo: valor.erro.codigo };
  // Erro do MCP sem envelope (texto livre com isError): nunca vira card nem "Concluída".
  if (ehObjeto(resposta) && (resposta.isError === true || (ehObjeto(resposta.result) && resposta.result.isError === true))) {
    return { tipo: "erro", codigo: "INDISPONIVEL" };
  }
  if (ehEnvelope(valor)) {
    const dados = ehObjeto(valor.dados) ? valor.dados : {};
    return {
      tipo: "envelope",
      envelope: { dados, fonte: valor.fonte, avisos: valor.avisos.filter((a) => typeof a === "string") },
    };
  }
  return { tipo: "cru", dados: ehObjeto(valor) ? valor : {} };
}
