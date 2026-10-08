import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MODELO_INICIAL, type ItemConversa, type ModeloSessao } from "../../sessao/modelo";
import { reducerSessao, type AcaoSessao } from "../../sessao/reducer";
import { sugestoesDoComposer } from "../../sessao/sugestoes";
import { gerarRoteiro } from "../../simulado/roteiro";
import { R_AVANCAR, SUGESTOES_POR_ESTADO } from "../../sessao/sugestoes-padrao";
import { agrupar, Conversa } from "./Conversa";

function modeloDoRoteiro(): ModeloSessao {
  const acoes: AcaoSessao[] = [];
  let agora = 1_790_000_000_000;
  for (const t of gerarRoteiro().turnos) {
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

const cliente = (chave: string, texto: string): ItemConversa => ({ tipo: "mensagem_cliente", chave, ts: 0, texto });
const agente = (chave: string): ItemConversa => ({ tipo: "mensagem_agente", chave, ts: 0, autor: "bussola", texto: "ok", emStreaming: false });
const ferramenta = (chave: string, nome: string): ItemConversa => ({
  tipo: "ferramenta",
  chave,
  ts: 0,
  chamadaId: chave,
  nome,
  args: {},
  status: "ok",
  inicio: 0,
  turno: 1,
});

describe("agrupar", () => {
  it("separa cliente e divisor e junta ferramentas seguidas num bloco", () => {
    const grupos = agrupar([
      cliente("c1", "oi"),
      ferramenta("f1", "perfil_financeiro"),
      ferramenta("f2", "capacidade_poupanca"),
      agente("a1"),
      ferramenta("f3", "simular_objetivo"),
      { tipo: "divisor_mes", chave: "d1", ts: 0, anomes: 202507 },
      agente("a2"),
    ]);
    expect(grupos.map((g) => g.tipo)).toEqual(["fora", "agente", "fora", "agente"]);
    const bloco = grupos[1];
    expect(bloco.tipo === "agente" && bloco.partes.map((p) => (p.tipo === "ferramentas" ? p.itens.length : p.item.tipo))).toEqual([
      2,
      "mensagem_agente",
      1,
    ]);
  });
});

describe("Conversa: roteiro canônico", () => {
  const modelo = modeloDoRoteiro();

  it("mostra cards de cada etapa com rótulos acessíveis (FR-030)", () => {
    render(<Conversa itens={modelo.itens} estado={modelo.estado} ocupado={false} lento={false} onEnviar={() => {}} onRepetir={() => {}} />);
    for (const nome of ["CardDiagnostico", "Simulação do objetivo financeiro", "Comparação de caminhos para o objetivo", "CardPlano", "CardPlanejadoRealizado"]) {
      expect(screen.getAllByLabelText(nome).length).toBeGreaterThan(0);
    }
    const mensagens = modelo.itens.filter((i) => i.tipo === "mensagem_cliente");
    expect(screen.getByText(mensagens[0].texto)).toBeInTheDocument();
  });

  it("não mostra as boas-vindas depois que o cliente falou", () => {
    render(
      <Conversa itens={modelo.itens} estado={modelo.estado} ocupado={false} lento={false} onEnviar={() => {}} onRepetir={() => {}} vazio={<p>boas-vindas</p>} />,
    );
    expect(screen.queryByText("boas-vindas")).not.toBeInTheDocument();
  });
});

describe("Conversa: leitura sem interrupção", () => {
  it("não move a rolagem quando a pessoa está lendo mensagens antigas", () => {
    const props = {
      estado: {},
      ocupado: false,
      lento: false,
      onEnviar: () => {},
      onRepetir: () => {},
    };
    const { rerender } = render(<Conversa {...props} itens={[cliente("c1", "oi"), agente("a1")]} />);
    const area = screen.getByRole("region", { name: "Conversa" });
    Object.defineProperty(area, "scrollHeight", { configurable: true, value: 1400 });
    Object.defineProperty(area, "clientHeight", { configurable: true, value: 400 });
    area.scrollTop = 200;
    fireEvent.scroll(area);

    rerender(<Conversa {...props} itens={[cliente("c1", "oi"), agente("a1"), agente("a2")]} />);
    expect(area.scrollTop).toBe(200);

    area.scrollTop = 1000;
    fireEvent.scroll(area);
    rerender(<Conversa {...props} itens={[cliente("c1", "oi"), agente("a1"), agente("a2"), agente("a3")]} />);
    expect(area.scrollTop).toBe(1400);
  });

  it("prioriza a mensagem nova do usuário mesmo quando ele estava lendo acima", () => {
    const props = {
      estado: {},
      ocupado: false,
      lento: false,
      onEnviar: () => {},
      onRepetir: () => {},
    };
    const { rerender } = render(<Conversa {...props} itens={[cliente("c1", "oi"), agente("a1")]} />);
    const area = screen.getByRole("region", { name: "Conversa" });
    Object.defineProperty(area, "scrollHeight", { configurable: true, value: 1400 });
    Object.defineProperty(area, "clientHeight", { configurable: true, value: 400 });
    area.scrollTop = 200;
    fireEvent.scroll(area);
    rerender(<Conversa {...props} itens={[cliente("c1", "oi"), agente("a1"), cliente("c2", "novo pedido")]} />);
    expect(area.scrollTop).toBe(1400);
  });
});

describe("Conversa: estados de espera", () => {
  it("mostra boas-vindas sem mensagens do cliente", () => {
    render(<Conversa itens={[]} estado={{}} ocupado={false} lento={false} onEnviar={() => {}} onRepetir={() => {}} vazio={<p>boas-vindas</p>} />);
    expect(screen.getByText("boas-vindas")).toBeInTheDocument();
  });

  it("indica digitação enquanto o agente não respondeu", () => {
    render(<Conversa itens={[cliente("c1", "oi")]} estado={{}} ocupado lento={false} onEnviar={() => {}} onRepetir={() => {}} />);
    expect(screen.getByRole("status", { name: "A Bússola está respondendo" })).toBeInTheDocument();
  });

  it("E5: skeleton enquanto uma consulta roda", () => {
    const consultando: ItemConversa = { ...(ferramenta("f1", "perfil_financeiro") as Extract<ItemConversa, { tipo: "ferramenta" }>), status: "consultando" };
    render(<Conversa itens={[cliente("c1", "oi"), consultando]} estado={{}} ocupado lento onEnviar={() => {}} onRepetir={() => {}} />);
    expect(screen.getByLabelText("Carregando resultado")).toBeInTheDocument();
  });

  it("falha de conexão oferece tentar de novo", async () => {
    const onRepetir = vi.fn();
    const falha: ItemConversa = { tipo: "falha_conexao", chave: "x", ts: 0, mensagem: "Não consegui falar com a Bússola agora.", reenviar: "oi" };
    render(<Conversa itens={[cliente("c1", "oi"), falha]} estado={{}} ocupado={false} lento={false} onEnviar={() => {}} onRepetir={onRepetir} />);
    const alerta = screen.getByRole("alert");
    await userEvent.click(within(alerta).getByRole("button", { name: /Tentar de novo/ }));
    expect(onRepetir).toHaveBeenCalledOnce();
  });
});

describe("sugestoesDoComposer", () => {
  it("não sugere nada antes do cliente falar", () => {
    expect(sugestoesDoComposer({ ...MODELO_INICIAL, estado: { estado_jornada: "OBJETIVO" } }, "simulado")).toEqual([]);
  });

  it("usa as respostas rápidas do turno atual", () => {
    const itens: ItemConversa[] = [cliente("c1", "oi"), { ...(agente("a1") as Extract<ItemConversa, { tipo: "mensagem_agente" }>), respostasRapidas: ["Sim"] }];
    expect(sugestoesDoComposer({ ...MODELO_INICIAL, itens, estado: { estado_jornada: "ENTENDER" } }, "simulado")).toEqual(["Sim"]);
    expect(sugestoesDoComposer({ ...MODELO_INICIAL, itens, estado: { estado_jornada: "ENTENDER" } }, "ao-vivo")).toEqual(["Sim"]);
  });

  it("cai nas sugestões da etapa e esconde o avanço sem plano", () => {
    const base = { ...MODELO_INICIAL, itens: [cliente("c1", "oi"), agente("a1")] };
    expect(
      sugestoesDoComposer({ ...base, estado: { estado_jornada: "ACOMPANHAR", plano_id: "p", ate_anomes: 202507 } }, "simulado"),
    ).toEqual(SUGESTOES_POR_ESTADO.ACOMPANHAR);
    expect(
      sugestoesDoComposer({ ...base, estado: { estado_jornada: "ACOMPANHAR", plano_id: "p", ate_anomes: 202512 } }, "simulado"),
    ).not.toContain(R_AVANCAR);
  });

  it("ao vivo não usa o roteiro do simulado: sem respostas rápidas do agente, nenhum chip (A4)", () => {
    const base = { ...MODELO_INICIAL, itens: [cliente("c1", "oi"), agente("a1")] };
    const estado = { estado_jornada: "ACOMPANHAR" as const, plano_id: "p", ate_anomes: 202507 };
    expect(sugestoesDoComposer({ ...base, estado }, "simulado")).toEqual(SUGESTOES_POR_ESTADO.ACOMPANHAR);
    expect(sugestoesDoComposer({ ...base, estado }, "ao-vivo")).toEqual([]);
  });

  it("não sugere nada com autorização pendente", () => {
    const base = { ...MODELO_INICIAL, itens: [cliente("c1", "oi"), agente("a1")] };
    const estado = { estado_jornada: "AGIR" as const, consentimentos: { criar_plano: { consent_id: "c", status: "pendente" as const } } };
    expect(sugestoesDoComposer({ ...base, estado }, "simulado")).toEqual([]);
  });
});
