import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { EventoAdk } from "../../agente/tipos";
import { mensagemTentarDeNovo } from "../../sessao/catalogo";
import { MODELO_INICIAL, type ItemFerramenta, type ModeloSessao } from "../../sessao/modelo";
import { reducerSessao, type AcaoSessao } from "../../sessao/reducer";
import { AgenteSimulado, relogioFixo, type Bordas } from "../../simulado/agente-simulado";
import { MENSAGENS_ROTEIRO } from "../../simulado/roteiro";
import { BlocoAnalise } from "./BlocoAnalise";
import { ErroFerramenta, erroVisivelNaConversa } from "./ErroFerramenta";

const AGORA = 1_790_000_000_000;
const DIAGNOSTICO = ["perfil_financeiro", "capacidade_poupanca", "dividas_e_parcelas", "oportunidades_corte"];
/** Texto técnico que um `erro.mensagem` real poderia trazer: nunca vai para a tela. */
const MENSAGEM_TECNICA = "SELECT * FROM `projeto-x.bussola_dados.transacoes` — tempo esgotado na consulta";
const PROIBIDOS = ["SELECT", "projeto-x", "tempo esgotado na consulta", "bussola_dados"];

function ev(evento: EventoAdk): AcaoSessao {
  return { tipo: "evento", evento, agora: AGORA };
}

function chamada(nome: string, id: string): EventoAdk {
  return { author: "bussola", content: { role: "model", parts: [{ functionCall: { id, name: nome, args: {} } }] } };
}

function resposta(nome: string, id: string, response: unknown): EventoAdk {
  return { author: "bussola", content: { role: "user", parts: [{ functionResponse: { id, name: nome, response } }] } };
}

function ferramentas(m: ModeloSessao): ItemFerramenta[] {
  return m.itens.filter((i): i is ItemFerramenta => i.tipo === "ferramenta");
}

/** Itens de ferramenta montados pelo reducer a partir de respostas cruas de erro. */
function itensComErroCru(): ItemFerramenta[] {
  const m = [
    ev(chamada("oportunidades_corte", "c1")),
    ev(chamada("dividas_e_parcelas", "c2")),
    ev(resposta("oportunidades_corte", "c1", { erro: { codigo: "INDISPONIVEL", mensagem: MENSAGEM_TECNICA } })),
    ev(resposta("dividas_e_parcelas", "c2", { result: { erro: { codigo: "BQ_TIMEOUT", mensagem: MENSAGEM_TECNICA } } })),
  ].reduce(reducerSessao, MODELO_INICIAL);
  return ferramentas(m);
}

async function sessaoSimulada(bordas: Partial<Bordas>) {
  const agente = new AgenteSimulado({ relogio: relogioFixo() });
  agente.configurarBordas(bordas);
  const inicio = await agente.iniciar();
  let agora = AGORA;
  let m = reducerSessao(MODELO_INICIAL, { tipo: "iniciada", estado: inicio.estado, eventos: inicio.eventos, agora });
  const enviar = async (texto: string) => {
    agora += 1000;
    m = reducerSessao(m, { tipo: "enviada", texto, agora });
    for await (const evento of agente.enviar(texto)) m = reducerSessao(m, { tipo: "evento", evento, agora });
    m = reducerSessao(m, { tipo: "turno_fim", estado: await agente.ressincronizar(), agora });
    return m;
  };
  for (const texto of MENSAGENS_ROTEIRO.slice(0, 2)) await enviar(texto);
  return { enviar, modelo: () => m };
}

function diagnosticoDoTurno(m: ModeloSessao, turno: number): ItemFerramenta[] {
  return ferramentas(m).filter((i) => i.turno === turno && DIAGNOSTICO.includes(i.nome));
}

describe("ErroFerramenta", () => {
  it("INDISPONIVEL mostra a copy pt-BR e 'Tentar de novo' envia a frase do catálogo", async () => {
    const onEnviar = vi.fn();
    const user = userEvent.setup();
    render(<ErroFerramenta nome="oportunidades_corte" codigo="INDISPONIVEL" onEnviar={onEnviar} />);
    const alerta = screen.getByRole("alert", { name: "ErroFerramenta" });
    expect(alerta).toHaveTextContent("Não consegui consultar oportunidades de corte agora. Sigo com o que tenho.");
    await user.click(within(alerta).getByRole("button", { name: "Tentar de novo" }));
    expect(onEnviar).toHaveBeenCalledTimes(1);
    expect(onEnviar).toHaveBeenCalledWith(mensagemTentarDeNovo("oportunidades_corte"));
    expect(onEnviar).toHaveBeenCalledWith("Tentar de novo: Oportunidades de corte");
  });

  it("'Tentar de novo' fica desabilitado com a sessão ocupada e some sem onEnviar", () => {
    const { rerender } = render(<ErroFerramenta nome="dividas_e_parcelas" codigo="INDISPONIVEL" onEnviar={vi.fn()} desabilitado />);
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeDisabled();
    rerender(<ErroFerramenta nome="dividas_e_parcelas" codigo="INDISPONIVEL" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Não consegui consultar dívidas e parcelas agora.");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it.each([
    ["ENTRADA_INVALIDA", "simular_objetivo", "Não entendi os valores desse pedido. Pode reformular?"],
    ["PRAZO_IMPLAUSIVEL", "simular_objetivo", "Esse prazo não é possível de simular. Tente outro prazo."],
    ["USUARIO_INEXISTENTE", "perfil_financeiro", "Não encontrei seus dados nesta demonstração."],
    ["SEM_PLANO_ATIVO", "avancar_mes", "Você ainda não tem um plano ativo. Crie o plano para acompanhar mês a mês."],
    ["FIM_DO_REPLAY", "avancar_mes", "A demonstração vai até dez/2025. Não há mais meses para avançar."],
    ["DADOS_INSUFICIENTES", "simular_objetivo", "Tenho poucos meses de histórico para estimar sua sobra com segurança."],
  ])("%s em %s vira aviso com a copy fixa, sem 'Tentar de novo'", (codigo, nome, copy) => {
    render(<ErroFerramenta nome={nome} codigo={codigo} onEnviar={vi.fn()} />);
    expect(screen.getByRole("note")).toHaveTextContent(copy);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tentar de novo" })).not.toBeInTheDocument();
  });

  it("código desconhecido vira a mensagem genérica", () => {
    render(<ErroFerramenta nome="resumo_mes" codigo="BQ_TIMEOUT" onEnviar={vi.fn()} />);
    expect(screen.getByRole("note")).toHaveTextContent("Algo deu errado nesta consulta. Sigo com o que tenho.");
    expect(document.body.textContent).not.toContain("BQ_TIMEOUT");
  });

  it("não aparece na conversa para consentimento pendente nem para histórico curto do diagnóstico", () => {
    expect(erroVisivelNaConversa("criar_plano", "CONSENTIMENTO_NECESSARIO")).toBe(false);
    expect(erroVisivelNaConversa("capacidade_poupanca", "DADOS_INSUFICIENTES")).toBe(false);
    expect(erroVisivelNaConversa("perfil_financeiro", "DADOS_INSUFICIENTES")).toBe(false);
    expect(erroVisivelNaConversa("oportunidades_corte", "INDISPONIVEL")).toBe(true);
    const { container, rerender } = render(<ErroFerramenta nome="criar_plano" codigo="CONSENTIMENTO_NECESSARIO" onEnviar={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ErroFerramenta nome="capacidade_poupanca" codigo="DADOS_INSUFICIENTES" onEnviar={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ErroFerramenta nome="perfil_financeiro" codigo="DADOS_INSUFICIENTES" onEnviar={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("erro.mensagem nunca chega à tela", () => {
  it("o reducer guarda só o código do erro", () => {
    const itens = itensComErroCru();
    expect(itens.map((i) => i.resposta)).toEqual([
      { tipo: "erro", codigo: "INDISPONIVEL" },
      { tipo: "erro", codigo: "BQ_TIMEOUT" },
    ]);
    const serializado = JSON.stringify(itens);
    for (const proibido of PROIBIDOS) expect(serializado).not.toContain(proibido);
  });

  it("BlocoAnalise com uma ferramenta em erro mostra só a copy do catálogo", () => {
    const [oportunidades] = itensComErroCru();
    render(<BlocoAnalise itens={[oportunidades]} onEnviar={vi.fn()} ocupado={false} />);
    const bloco = screen.getByLabelText("Oportunidades de corte");
    expect(within(bloco).getByRole("img", { name: "Falhou" })).toBeInTheDocument();
    expect(within(bloco).getByRole("alert")).toHaveTextContent("Não consegui consultar oportunidades de corte agora. Sigo com o que tenho.");
    for (const proibido of PROIBIDOS) expect(document.body.textContent).not.toContain(proibido);
  });

  it("BlocoAnalise com várias ferramentas, aberto, também não mostra SQL, projeto nem a mensagem crua", async () => {
    const user = userEvent.setup();
    render(<BlocoAnalise itens={itensComErroCru()} onEnviar={vi.fn()} ocupado={false} />);
    await user.click(screen.getByRole("button", { name: /Analisei sua situação · 2 consultas/ }));
    expect(screen.getAllByRole("img", { name: "Falhou" })).toHaveLength(2);
    expect(screen.getByRole("alert")).toHaveTextContent("Não consegui consultar oportunidades de corte agora.");
    expect(screen.getByRole("note")).toHaveTextContent("Algo deu errado nesta consulta. Sigo com o que tenho.");
    for (const proibido of PROIBIDOS) expect(document.body.textContent).not.toContain(proibido);
  });

  it("mesmo se uma resposta vier com `mensagem` junto do código, a tela não a usa", () => {
    const [base] = itensComErroCru();
    const vazado = { ...base, resposta: { tipo: "erro", codigo: "INDISPONIVEL", mensagem: MENSAGEM_TECNICA } } as ItemFerramenta;
    render(<BlocoAnalise itens={[vazado]} onEnviar={vi.fn()} ocupado={false} />);
    for (const proibido of PROIBIDOS) expect(document.body.textContent).not.toContain(proibido);
  });

  it("texto de erro fora do formato do envelope não aparece na linha da ferramenta", () => {
    const m = [
      ev(chamada("resumo_mes", "c9")),
      ev(resposta("resumo_mes", "c9", { content: [{ type: "text", text: MENSAGEM_TECNICA }], isError: true })),
    ].reduce(reducerSessao, MODELO_INICIAL);
    render(<BlocoAnalise itens={ferramentas(m)} onEnviar={vi.fn()} ocupado={false} />);
    expect(screen.getByLabelText("Resumo do mês")).toBeInTheDocument();
    for (const proibido of PROIBIDOS) expect(document.body.textContent).not.toContain(proibido);
  });
});

describe("bordas do simulado no BlocoAnalise", () => {
  it("E3: diagnóstico com oportunidades de corte fora do ar e 'Tentar de novo' que resolve no turno seguinte", async () => {
    const sessao = await sessaoSimulada({ e3: true });
    const m = sessao.modelo();
    const diagnostico = diagnosticoDoTurno(m, m.turno);
    expect(diagnostico.map((i) => i.nome).sort()).toEqual([...DIAGNOSTICO].sort());

    const onEnviar = vi.fn();
    const user = userEvent.setup();
    const { unmount } = render(<BlocoAnalise itens={diagnostico} onEnviar={onEnviar} ocupado={false} />);
    await user.click(screen.getByRole("button", { name: /^Analisei sua situação · 4 consultas/ }));
    expect(screen.getAllByRole("img", { name: "Concluída" })).toHaveLength(3);
    expect(screen.getByRole("img", { name: "Falhou" })).toBeInTheDocument();
    const alerta = screen.getByRole("alert", { name: "ErroFerramenta" });
    expect(alerta).toHaveTextContent("Não consegui consultar oportunidades de corte agora. Sigo com o que tenho.");
    expect(document.body.textContent).not.toContain("tempo esgotado");

    await user.click(within(alerta).getByRole("button", { name: "Tentar de novo" }));
    expect(onEnviar).toHaveBeenCalledWith("Tentar de novo: Oportunidades de corte");
    unmount();

    const depois = await sessao.enviar(onEnviar.mock.calls[0][0] as string);
    const novas = ferramentas(depois).filter((i) => i.turno === depois.turno);
    expect(novas.map((i) => [i.nome, i.status])).toEqual([["oportunidades_corte", "ok"]]);
    render(<BlocoAnalise itens={novas} onEnviar={onEnviar} ocupado={false} />);
    expect(screen.getByRole("img", { name: "Concluída" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("E4: capacidade de poupança com histórico curto fica 'Com ressalva', sem alerta vermelho", async () => {
    const sessao = await sessaoSimulada({ e4: true });
    const m = sessao.modelo();
    const user = userEvent.setup();
    render(<BlocoAnalise itens={diagnosticoDoTurno(m, m.turno)} onEnviar={vi.fn()} ocupado={false} />);
    await user.click(screen.getByRole("button", { name: /^Analisei sua situação · 4 consultas/ }));
    const capacidade = screen.getByText("Capacidade de poupança").closest(".tool-line") as HTMLElement;
    expect(within(capacidade).getByRole("img", { name: "Com ressalva" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Falhou" })).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("E3 com a sessão ocupada: 'Tentar de novo' desabilitado", async () => {
    const sessao = await sessaoSimulada({ e3: true });
    const m = sessao.modelo();
    render(<BlocoAnalise itens={diagnosticoDoTurno(m, m.turno)} onEnviar={vi.fn()} ocupado />);
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeDisabled();
  });
});
