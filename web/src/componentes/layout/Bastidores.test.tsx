import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MODELO_INICIAL, type ModeloSessao } from "../../sessao/modelo";
import { reducerSessao } from "../../sessao/reducer";
import { AgenteSimulado, relogioFixo } from "../../simulado/agente-simulado";
import { MENSAGENS_ROTEIRO } from "../../simulado/roteiro";
import { ABAS, Bastidores } from "./Bastidores";

const AGORA = 1_790_000_000_000;
// UUID v4 completo montado em partes, como no reducer.test.
const UUID_CLIENTE = "36a2b1c4-0000-4000-8000-00000000" + "7269";
const UUID_V4 = /[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i;
const HORA_SEGUNDOS = /^\d{2}:\d{2}:\d{2}$/;

/** Sessão no simulado até "Avançar um mês" (julho, com desvio), aplicada no reducer. */
async function sessaoAteODesvio(): Promise<ModeloSessao> {
  const agente = new AgenteSimulado({ relogio: relogioFixo() });
  const inicio = await agente.iniciar();
  let agora = AGORA;
  let m = reducerSessao(MODELO_INICIAL, { tipo: "iniciada", estado: inicio.estado, eventos: inicio.eventos, agora });
  for (const texto of MENSAGENS_ROTEIRO.slice(0, 6)) {
    agora += 1000;
    m = reducerSessao(m, { tipo: "enviada", texto, agora });
    for await (const evento of agente.enviar(texto)) m = reducerSessao(m, { tipo: "evento", evento, agora });
    m = reducerSessao(m, { tipo: "turno_fim", estado: await agente.ressincronizar(), agora });
  }
  return m;
}

/** Modelo montado à mão com o UUID completo do cliente em todo lugar que chega aos Bastidores. */
function modeloComUuidCompleto(): ModeloSessao {
  return {
    ...MODELO_INICIAL,
    estado: {
      id_usuario: UUID_CLIENTE,
      ate_anomes: 202507,
      estado_jornada: "AGIR",
      objetivo: { tipo: "imovel", descricao: "Primeiro apartamento", valor_alvo: 30000, prazo_meses: 24 },
      cenario_escolhido: "acelerado",
      plano_id: "9f1c2d3e-1111-4222-8333-44445555" + "6666",
      consentimentos: { criar_plano: { consent_id: "c0ffee00-aaaa-4bbb-8ccc-dddd0000" + "eeee", status: "aceito" } },
    },
    jornada: [{ estado: "OBJETIVO", ts: AGORA }],
    ferramentas: [
      {
        chamadaId: "ch-1",
        nome: "perfil_financeiro",
        args: { id_usuario: UUID_CLIENTE, ate_anomes: 202507 },
        status: "ok",
        inicio: AGORA,
        fim: AGORA + 412,
        fonte: { ferramenta: "perfil_financeiro", tabelas: ["bussola_dados.perfil_mensal"], periodo: { inicio: 202501, fim: 202507 } },
        avisos: ["histórico curto"],
      },
      { chamadaId: "ch-2", nome: "avancar_mes", args: { id_usuario: UUID_CLIENTE }, status: "erro", inicio: AGORA, fim: AGORA + 90, avisos: [], codigoErro: "INDISPONIVEL" },
    ],
    auditoria: [
      { tipo_evento: "sessao_iniciada", ts: AGORA, resumo: "sessão da demonstração" },
      { tipo_evento: "consentimento_decidido", ts: AGORA + 1000, estado_jornada: "AGIR", resumo: "criar_plano · aceito" },
    ],
  };
}

function renderizar(modelo: ModeloSessao, variante: "painel" | "folha" = "painel") {
  const onFechar = vi.fn();
  const user = userEvent.setup();
  const tela = render(<Bastidores modelo={modelo} variante={variante} onFechar={onFechar} apresentador={<div>Apresentador</div>} />);
  return { ...tela, onFechar, user };
}

function abas() {
  return within(screen.getByRole("navigation", { name: "Seções dos Bastidores" })).getAllByRole("button");
}

describe("Bastidores", () => {
  it("mostra as quatro abas com Jornada ativa por padrão", async () => {
    renderizar(await sessaoAteODesvio());
    expect(abas().map((b) => b.textContent)).toEqual([...ABAS]);
    expect(abas()).toHaveLength(4);
    expect(screen.getByRole("button", { name: "Jornada" })).toHaveAttribute("aria-current", "true");
    for (const nome of ["Ferramentas", "Consentimentos", "Auditoria"]) {
      expect(screen.getByRole("button", { name: nome })).not.toHaveAttribute("aria-current");
    }
    const jornada = screen.getByRole("list", { name: "Estados da jornada" });
    expect(within(jornada).getAllByRole("listitem")).toHaveLength(6);
    expect(within(jornada).getByText("estado atual")).toBeInTheDocument();
  });

  it("rodapé mostra o cliente mascarado e o mês de referência", async () => {
    renderizar(await sessaoAteODesvio());
    const cliente = screen.getByText("Cliente").parentElement;
    expect(cliente).not.toBeNull();
    expect(within(cliente as HTMLElement).getByText("36a2…7269")).toBeInTheDocument();
    const mes = screen.getByText("Mês de ref.").parentElement as HTMLElement;
    expect(within(mes).getByText("jul/2025")).toBeInTheDocument();
  });

  it("com o UUID completo no state, nenhuma aba nem o rodapé exibe um UUID v4", async () => {
    const { container, user } = renderizar(modeloComUuidCompleto());
    for (const aba of ABAS) {
      await user.click(screen.getByRole("button", { name: aba }));
      expect(screen.getByRole("button", { name: aba })).toHaveAttribute("aria-current", "true");
      expect(container.textContent).not.toMatch(UUID_V4);
      expect(document.body.textContent).not.toMatch(UUID_V4);
    }
    expect(screen.getByText("36a2…7269")).toBeInTheDocument();
  });

  it("aba Ferramentas mostra nomes técnicos, parâmetros mascarados, fonte e o código de erro", async () => {
    const { user } = renderizar(modeloComUuidCompleto());
    await user.click(screen.getByRole("button", { name: "Ferramentas" }));
    expect(screen.getByText("perfil_financeiro")).toBeInTheDocument();
    expect(screen.getByText("avancar_mes")).toBeInTheDocument();
    expect(screen.getByText("id_usuario=36a2…7269 · ate_anomes=202507")).toBeInTheDocument();
    expect(screen.getByText("ok · 412 ms")).toBeInTheDocument();
    expect(screen.getByText(/INDISPONIVEL/)).toBeInTheDocument();
    expect(screen.getByText("bussola_dados.perfil_mensal · jan–jul/2025")).toBeInTheDocument();
    expect(screen.getByText("aviso: histórico curto")).toBeInTheDocument();
  });

  it("trocar de aba mostra ferramentas da sessão e a auditoria do mais recente", async () => {
    const { user } = renderizar(await sessaoAteODesvio());

    await user.click(screen.getByRole("button", { name: "Ferramentas" }));
    expect(screen.getByRole("button", { name: "Ferramentas" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("button", { name: "Jornada" })).not.toHaveAttribute("aria-current");
    expect(screen.getAllByText("oportunidades_corte").length).toBeGreaterThan(0);
    expect(screen.getAllByText("avancar_mes").length).toBeGreaterThan(0);
    expect(screen.queryByText("Nenhuma ferramenta chamada ainda. Conte um objetivo na conversa.")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Consentimentos" }));
    expect(screen.getByText("criar_plano")).toBeInTheDocument();
    expect(screen.getByText("aceito")).toBeInTheDocument();
    expect(screen.getByText("Regra de governança")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Auditoria" }));
    const lista = screen.getByRole("list", { name: "Eventos de auditoria, do mais recente" });
    const itens = within(lista).getAllByRole("listitem");
    expect(itens.slice(0, 3).map((li) => li.querySelector(".tl-title .mono")?.textContent)).toEqual([
      "rota_recalculada",
      "desvio_detectado",
      "acompanhamento_mes_avancado",
    ]);
    expect(within(itens[1]).getByText("causa: Viagens · ACOMPANHAR")).toBeInTheDocument();
    for (const li of itens) expect(within(li).getByText(HORA_SEGUNDOS)).toBeInTheDocument();
    expect(itens.at(-1)?.textContent).toContain("sessao_iniciada");
  });

  it("sessão vazia mostra os textos de estado vazio em pt-BR", async () => {
    const { user } = renderizar(MODELO_INICIAL);
    await user.click(screen.getByRole("button", { name: "Ferramentas" }));
    expect(screen.getByText("Nenhuma ferramenta chamada ainda. Conte um objetivo na conversa.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Consentimentos" }));
    expect(screen.getByText("Nenhum consentimento pedido ainda.")).toBeInTheDocument();
    expect(screen.getByText("36a2…7269")).toBeInTheDocument();
  });

  it("variante folha é um diálogo com 'Fechar Bastidores' em foco e Escape fecha", async () => {
    const { onFechar, user } = renderizar(await sessaoAteODesvio(), "folha");
    const dialogo = screen.getByRole("dialog", { name: "Bastidores" });
    expect(dialogo).toHaveAttribute("aria-modal", "true");
    const fechar = within(dialogo).getByRole("button", { name: "Fechar Bastidores" });
    expect(fechar).toHaveFocus();
    // rótulos curtos na folha, mas o nome acessível segue completo
    expect(within(dialogo).getByRole("button", { name: "Ferramentas" })).toHaveTextContent("Ferram.");
    expect(within(dialogo).getByRole("button", { name: "Consentimentos" })).toHaveTextContent("Consent.");
    expect(within(dialogo).getByText("Apresentador")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(onFechar).toHaveBeenCalledTimes(1);
    await user.click(fechar);
    expect(onFechar).toHaveBeenCalledTimes(2);
  });

  it("mantém o foco no diálogo e restaura o controle anterior no fechamento", async () => {
    const disparador = document.createElement("button");
    disparador.textContent = "Abrir painel";
    document.body.appendChild(disparador);
    disparador.focus();
    const { user, unmount } = renderizar(modeloComUuidCompleto(), "folha");
    const dialogo = screen.getByRole("dialog", { name: "Bastidores" });
    const botoes = within(dialogo).getAllByRole("button");
    expect(botoes[0]).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");

    await user.tab({ shift: true });
    expect(botoes.at(-1)).toHaveFocus();
    await user.tab();
    expect(botoes[0]).toHaveFocus();

    unmount();
    expect(disparador).toHaveFocus();
    expect(document.body.style.overflow).not.toBe("hidden");
    disparador.remove();
  });

  it("variante painel é um aside com 'Recolher Bastidores' e Escape não fecha", async () => {
    const { onFechar, user } = renderizar(await sessaoAteODesvio());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Bastidores" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(onFechar).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Recolher Bastidores" }));
    expect(onFechar).toHaveBeenCalledTimes(1);
  });

  it("parâmetro aninhado com o UUID do cliente também sai mascarado", async () => {
    const modelo: ModeloSessao = {
      ...modeloComUuidCompleto(),
      ferramentas: [
        { chamadaId: "ch-9", nome: "simular_objetivo", args: { filtro: { id_usuario: UUID_CLIENTE } }, status: "ok", inicio: AGORA, fim: AGORA + 5, avisos: [] },
        { chamadaId: "ch-10", nome: "resumo_mes", args: { ids: [UUID_CLIENTE], nota: `cliente ${UUID_CLIENTE}` }, status: "ok", inicio: AGORA, fim: AGORA + 5, avisos: [] },
      ],
    };
    const { container, user } = renderizar(modelo);
    await user.click(screen.getByRole("button", { name: "Ferramentas" }));
    expect(container.textContent).not.toMatch(UUID_V4);
    expect(container.textContent).toContain("36a2…7269");
  });
});
