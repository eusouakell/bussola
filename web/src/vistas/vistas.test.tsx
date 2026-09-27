// T052: vistas P1–P5 leem o plano criado (FR-024), sem calcular (FR-007).
// Os modelos saem do agente simulado com relógio fixo passando pelo reducer.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { dadosDe, fonteDe } from "../agente/envelope";
import type { Dados, EventoAdk, RespostaFerramenta } from "../agente/tipos";
import { rotuloFonte } from "../componentes/base/ChipFonte";
import { brl, meses, mesAbrev } from "../formatacao/formatar";
import { MODELO_INICIAL, type ModeloSessao } from "../sessao/modelo";
import { reducerSessao, type AcaoSessao } from "../sessao/reducer";
import { MotorSimulado, relogioFixo } from "../simulado/agente-simulado";
import { gerarRoteiro, MENSAGENS_ROTEIRO } from "../simulado/roteiro";
import { R_AVANCAR, R_LEMBRETES, R_STATUS } from "../sessao/sugestoes-padrao";
import { R_OUTRO_OBJETIVO } from "./P1Encerramento";
import { VISTAS, Vistas, type NomeVista } from "./Vistas";

const ROTULOS: Record<NomeVista, string> = {
  encerramento: "P1Encerramento",
  "meu-plano": "P2MeuPlano",
  trilha: "P3Trilha",
  resumo: "P4Resumo",
  "check-in": "P5CheckIn",
};

function reduzir(turnos: { mensagem: string | null; eventos: EventoAdk[] }[]): ModeloSessao {
  const acoes: AcaoSessao[] = [];
  let agora = 1_790_000_000_000;
  for (const t of turnos) {
    agora += 1000;
    if (t.mensagem === null) {
      acoes.push({ tipo: "iniciada", estado: {}, eventos: t.eventos, agora });
      continue;
    }
    acoes.push({ tipo: "enviada", texto: t.mensagem, agora });
    for (const evento of t.eventos) acoes.push({ tipo: "evento", evento, agora });
    acoes.push({ tipo: "turno_fim", agora });
  }
  return acoes.reduce(reducerSessao, MODELO_INICIAL);
}

/** Roteiro até a mensagem `n` (5 = plano criado com a autorização). */
function modeloAte(n: number): ModeloSessao {
  const motor = new MotorSimulado(relogioFixo());
  const turnos: { mensagem: string | null; eventos: EventoAdk[] }[] = [{ mensagem: null, eventos: motor.iniciar() }];
  for (const m of MENSAGENS_ROTEIRO.slice(0, n)) turnos.push({ mensagem: m, eventos: motor.turno(m) });
  return reduzir(turnos);
}

/** Respostas ok de uma ferramenta, na ordem da conversa. */
function respostasDas(modelo: ModeloSessao, nome: string): RespostaFerramenta[] {
  return modelo.itens.flatMap((i) =>
    i.tipo === "ferramenta" && i.nome === nome && i.status === "ok" && i.resposta ? [i.resposta] : [],
  );
}

function dadosDas(modelo: ModeloSessao, nome: string): Dados[] {
  return respostasDas(modelo, nome).map(dadosDe);
}

/** Nome acessível do chip de fonte compacto da última resposta da ferramenta. */
function chipDa(modelo: ModeloSessao, nome: string): string {
  const fonte = fonteDe(respostasDas(modelo, nome).at(-1));
  if (!fonte) throw new Error(`sem fonte para ${nome}`);
  return `Fonte: ${rotuloFonte(fonte)}`;
}

function renderizar(modelo: ModeloSessao, vista: NomeVista) {
  const props = { onVista: vi.fn(), onConversa: vi.fn(), onEnviar: vi.fn() };
  const r = render(<Vistas vista={vista} modelo={modelo} {...props} />);
  return { ...r, ...props };
}

const PLANO_CRIADO = modeloAte(5);
const JORNADA = reduzir(gerarRoteiro().turnos);
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

describe("Vistas: sem plano", () => {
  it.each(VISTAS.map((v) => v.nome))("%s mostra EstadoVazio e o botão volta para a conversa", (vista) => {
    const { onConversa, onEnviar } = renderizar(MODELO_INICIAL, vista);
    const vazio = screen.getByRole("region", { name: "EstadoVazio" });
    expect(screen.queryByRole("region", { name: ROTULOS[vista] })).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Seções do plano" })).toBeNull();
    fireEvent.click(within(vazio).getByRole("button", { name: "Voltar para a conversa" }));
    expect(onConversa).toHaveBeenCalledTimes(1);
    expect(onEnviar).not.toHaveBeenCalled();
  });

  it("o plano ainda não autorizado continua vazio", () => {
    renderizar(modeloAte(4), "meu-plano");
    expect(screen.getByRole("region", { name: "EstadoVazio" })).toBeInTheDocument();
  });
});

describe("Vistas: plano criado", () => {
  it("P2MeuPlano mostra meta, aporte e prazo iguais à resposta de criar_plano, com fonte", () => {
    const [criado] = dadosDas(PLANO_CRIADO, "criar_plano");
    expect(criado).toBeDefined();
    renderizar(PLANO_CRIADO, "meu-plano");
    const vista = screen.getByRole("region", { name: "P2MeuPlano" });
    const texto = vista.textContent ?? "";
    expect(texto).toContain(brl(criado.valor_alvo as number));
    expect(texto).toContain(brl(criado.aporte_mensal as number));
    expect(texto).toContain(meses(criado.prazo_meses as number));
    expect(texto).toContain("Primeiro apartamento");
    // Cada KPI tem o chip de fonte do envelope de criar_plano.
    expect(within(vista).getAllByRole("button", { name: chipDa(PLANO_CRIADO, "criar_plano") }).length).toBeGreaterThanOrEqual(3);
    // Sem mês acompanhado: nada de progresso inventado.
    expect(texto).not.toContain("Guardado até agora");
    expect(texto).toContain("Nenhum mês acompanhado ainda");
  });

  it("navegação: seções chamam onVista, Conversar e Voltar chamam onConversa", () => {
    const { onVista, onConversa } = renderizar(PLANO_CRIADO, "meu-plano");
    const nav = screen.getByRole("navigation", { name: "Seções do plano" });
    const nomes = within(nav)
      .getAllByRole("button")
      .map((b) => b.textContent);
    expect(nomes).toEqual(["Jornada", "Trilha", "Resumo", "Check-in", "Conversar"]);
    fireEvent.click(within(nav).getByRole("button", { name: "Trilha" }));
    fireEvent.click(within(nav).getByRole("button", { name: "Check-in" }));
    expect(onVista.mock.calls).toEqual([["trilha"], ["check-in"]]);
    fireEvent.click(within(nav).getByRole("button", { name: "Conversar" }));
    fireEvent.click(screen.getByRole("button", { name: "Voltar para a conversa" }));
    expect(onConversa).toHaveBeenCalledTimes(2);
  });

  it("P1Encerramento abre Meu plano e manda textos que o agente entende", () => {
    const { onVista, onEnviar } = renderizar(PLANO_CRIADO, "encerramento");
    const vista = screen.getByRole("region", { name: "P1Encerramento" });
    fireEvent.click(within(vista).getByRole("button", { name: "Abrir Meu plano" }));
    expect(onVista).toHaveBeenCalledWith("meu-plano");
    fireEvent.click(within(vista).getByRole("button", { name: R_LEMBRETES }));
    fireEvent.click(within(vista).getByRole("button", { name: "Começar outro objetivo" }));
    expect(onEnviar.mock.calls).toEqual([[R_LEMBRETES], [R_OUTRO_OBJETIVO]]);
  });
});

describe("Vistas: jornada completa (ajuste e dois meses)", () => {
  it.each(VISTAS.map((v) => v.nome))("%s renderiza com o aria-label do componente, sem UUID nem promessa", (vista) => {
    renderizar(JORNADA, vista);
    const raiz = screen.getByRole("region", { name: ROTULOS[vista] });
    const texto = document.body.textContent ?? "";
    expect(raiz).toBeInTheDocument();
    expect(texto).not.toMatch(UUID);
    expect(texto).not.toMatch(/garantido|aprovado|contrate agora/i);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("P2MeuPlano usa o aporte do ajuste e o progresso do último mês", () => {
    const [ajuste] = dadosDas(JORNADA, "ajustar_plano");
    const mesesLidos = dadosDas(JORNADA, "avancar_mes");
    const ultimo = mesesLidos.at(-1) as Dados;
    renderizar(JORNADA, "meu-plano");
    const vista = screen.getByRole("region", { name: "P2MeuPlano" });
    const texto = vista.textContent ?? "";
    expect(texto).toContain(brl(ajuste.aporte_mensal as number));
    expect(texto).toContain(meses(ajuste.prazo_meses as number));
    expect(texto).toContain(brl(ultimo.acumulado as number));
    expect(texto).toContain(brl(ultimo.restante as number));
    expect(texto).toContain("Acima do plano");
    expect(within(vista).getAllByRole("button", { name: chipDa(JORNADA, "ajustar_plano") }).length).toBeGreaterThan(0);
    expect(within(vista).getByRole("button", { name: chipDa(JORNADA, "avancar_mes") })).toBeInTheDocument();
  });

  it("P3Trilha lista criação, ajuste e os meses com planejado × realizado da resposta", () => {
    const mesesLidos = dadosDas(JORNADA, "avancar_mes");
    renderizar(JORNADA, "trilha");
    const vista = screen.getByRole("region", { name: "P3Trilha" });
    const texto = vista.textContent ?? "";
    expect(texto).toContain("PLANO CRIADO");
    expect(texto).toContain("PLANO AJUSTADO · ROTA A");
    for (const m of mesesLidos) {
      expect(texto).toContain(mesAbrev(m.anomes as number).toUpperCase());
      expect(texto).toContain(brl(m.planejado as number));
      expect(texto).toContain(brl(m.realizado as number));
    }
    expect(texto).toContain("Abaixo do plano");
    expect(texto).toContain("Acima do plano");
  });

  it("P4Resumo mostra caminho, premissas, fontes e autorizações mascaradas", () => {
    renderizar(JORNADA, "resumo");
    const vista = screen.getByRole("region", { name: "P4Resumo" });
    const texto = vista.textContent ?? "";
    expect(texto).toContain("Acelerado");
    expect(texto).toContain("Sem rendimento considerado");
    expect(texto).toContain("Criar e acompanhar o plano");
    expect(texto).toContain("Ajustar o plano");
    expect(within(vista).getAllByText("Autorizado").length).toBe(2);
    const consentimentos = Object.values(JORNADA.estado.consentimentos ?? {});
    expect(consentimentos.length).toBe(2);
  });

  it("P5CheckIn mostra o aporte vigente e só manda textos ao agente", () => {
    const [ajuste] = dadosDas(JORNADA, "ajustar_plano");
    const { onEnviar } = renderizar(JORNADA, "check-in");
    const vista = screen.getByRole("region", { name: "P5CheckIn" });
    expect(vista.textContent).toContain(brl(ajuste.aporte_mensal as number));
    fireEvent.click(within(vista).getByRole("button", { name: R_AVANCAR }));
    fireEvent.click(within(vista).getByRole("button", { name: R_STATUS }));
    fireEvent.click(within(vista).getByRole("button", { name: R_LEMBRETES }));
    expect(onEnviar.mock.calls).toEqual([[R_AVANCAR], [R_STATUS], [R_LEMBRETES]]);
  });
});
