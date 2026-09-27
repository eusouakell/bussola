// Escolha do transporte pelo modo. Ficava em `sessao/useSessao.ts`, o que fazia
// a aplicação importar as duas implementações concretas (R3/R5).
import { CONFIG } from "../config";
import { AgenteSimulado } from "../simulado/agente-simulado";
import { ClienteAdk } from "./cliente-adk";
import { SEM_BORDAS, type Bordas, type Modo, type Transporte } from "./transporte";

/** `usuario` separa a conversa lembrada por persona logada no BFF. */
export function criarTransporte(modo: Modo, bordas: Bordas = SEM_BORDAS, usuario: string = CONFIG.usuarioAdk): Transporte {
  if (modo === "ao-vivo") {
    return new ClienteAdk({ app: CONFIG.app, usuario, base: CONFIG.baseApi });
  }
  const simulado = new AgenteSimulado({ parciais: true, atrasoMs: CONFIG.atrasoSimuladoMs });
  simulado.configurarBordas(bordas);
  return simulado;
}
