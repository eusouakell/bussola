// Hook da sessão (T028): escolhe o transporte, aplica os eventos no reducer
// e expõe enviar, parar, repetir, trocar de modo e as bordas do simulado.
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { SEM_BORDAS, type Bordas, type FabricaTransporte, type Modo, type Transporte } from "../agente/transporte";
import { CONFIG } from "../config";
import { MENSAGEM_FALHA_CONEXAO } from "./catalogo";
import { MODELO_INICIAL, type ModeloSessao } from "./modelo";
import { reducerSessao } from "./reducer";

export interface Sessao {
  modelo: ModeloSessao;
  modo: Modo;
  /** A sessão já recebeu o state inicial. */
  pronta: boolean;
  bordas: Bordas;
  enviar: (texto: string) => void;
  parar: () => void;
  /** Reenvia a última mensagem que falhou por conexão. */
  repetir: () => void;
  trocarModo: (modo: Modo) => void;
  reiniciar: () => void;
  configurarBordas: (bordas: Partial<Bordas>) => void;
}

export interface OpcoesSessao {
  /**
   * `false` segura o modo ao vivo até o login no BFF: nenhuma sessão é criada
   * no agente. O simulado não depende disso.
   */
  aoVivoLiberado?: boolean;
}

export function useSessao(
  modoInicial: Modo = CONFIG.modo,
  fabrica: FabricaTransporte,
  { aoVivoLiberado = true }: OpcoesSessao = {},
): Sessao {
  const [modo, setModo] = useState<Modo>(modoInicial);
  const [geracao, setGeracao] = useState(0);
  const [bordas, setBordas] = useState<Bordas>(SEM_BORDAS);
  const [modelo, despachar] = useReducer(reducerSessao, MODELO_INICIAL);
  const transporte = useRef<Transporte | null>(null);
  const controle = useRef<AbortController | null>(null);
  const bordasRef = useRef<Bordas>(SEM_BORDAS);
  const ocupadoRef = useRef(false);

  const aguardando = modo === "ao-vivo" && !aoVivoLiberado;

  useEffect(() => {
    if (aguardando) return;
    let viva = true;
    const t = fabrica(modo, bordasRef.current);
    transporte.current = t;
    t.iniciar()
      .then((inicio) => {
        if (viva) despachar({ tipo: "iniciada", estado: inicio.estado, eventos: inicio.eventos, agora: Date.now() });
      })
      .catch(() => {
        if (viva) despachar({ tipo: "falha", mensagem: MENSAGEM_FALHA_CONEXAO, agora: Date.now() });
      });
    return () => {
      viva = false;
      controle.current?.abort();
      if (transporte.current === t) transporte.current = null;
    };
  }, [modo, geracao, fabrica, aguardando]);

  const enviar = useCallback((texto: string) => {
    const limpo = texto.trim();
    const t = transporte.current;
    if (!limpo || !t || ocupadoRef.current) return;
    const abortar = new AbortController();
    controle.current = abortar;
    ocupadoRef.current = true;
    despachar({ tipo: "enviada", texto: limpo, agora: Date.now() });
    void (async () => {
      try {
        for await (const evento of t.enviar(limpo, abortar.signal)) {
          if (abortar.signal.aborted) break;
          despachar({ tipo: "evento", evento, agora: Date.now() });
        }
        if (transporte.current !== t) return;
        const estado = t.ressincronizar ? await t.ressincronizar().catch(() => null) : null;
        if (transporte.current !== t) return;
        despachar({ tipo: "turno_fim", estado, agora: Date.now() });
      } catch {
        if (transporte.current === t) {
          despachar({ tipo: "falha", mensagem: MENSAGEM_FALHA_CONEXAO, reenviar: limpo, agora: Date.now() });
        }
      } finally {
        // Só o turno corrente libera: um turno antigo abortado não solta o novo.
        if (controle.current === abortar) {
          controle.current = null;
          ocupadoRef.current = false;
        }
      }
    })();
  }, []);

  const parar = useCallback(() => {
    controle.current?.abort();
  }, []);

  const reiniciar = useCallback(() => {
    controle.current?.abort();
    controle.current = null;
    ocupadoRef.current = false;
    despachar({ tipo: "reiniciar" });
    setGeracao((g) => g + 1);
  }, []);

  /** Só a última falha conta; sem texto para reenviar, a sessão recomeça. */
  const repetir = useCallback(() => {
    const falha = modelo.itens.findLast((i) => i.tipo === "falha_conexao");
    if (!falha) return;
    if (falha.reenviar) enviar(falha.reenviar);
    else reiniciar();
  }, [modelo.itens, enviar, reiniciar]);

  const trocarModo = useCallback(
    (novo: Modo) => {
      if (novo === modo) return;
      controle.current?.abort();
      ocupadoRef.current = false;
      despachar({ tipo: "reiniciar" });
      setModo(novo);
    },
    [modo],
  );

  const configurarBordas = useCallback((parcial: Partial<Bordas>) => {
    const novas = { ...bordasRef.current, ...parcial };
    bordasRef.current = novas;
    setBordas(novas);
    transporte.current?.configurarBordas?.(parcial);
  }, []);

  const pronta = modelo.auditoria.some((e) => e.tipo_evento === "sessao_iniciada");
  return { modelo, modo, pronta, bordas, enviar, parar, repetir, trocarModo, reiniciar, configurarBordas };
}
