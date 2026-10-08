// Casca da aplicação (Main.dc.html no desktop, M*.dc.html abaixo de 1024 px):
// conversa, stepper, composer, Bastidores com a barra do apresentador e as
// vistas do plano (P1–P5), sem roteador.
import { useState } from "react";
import { criarTransporte } from "./agente/fabrica";
import { TelaLogin } from "./auth/TelaLogin";
import { ClienteAuth } from "./auth/clienteAuth";
import { useAuth } from "./auth/useAuth";
import { BoasVindas } from "./componentes/conversa/BoasVindas";
import { Conversa } from "./componentes/conversa/Conversa";
import { StepperJornada } from "./componentes/jornada/StepperJornada";
import { Ambiente } from "./componentes/layout/Ambiente";
import { BarraDemo } from "./componentes/layout/BarraDemo";
import { Bastidores } from "./componentes/layout/Bastidores";
import { Composer } from "./componentes/layout/Composer";
import { HeaderBussola } from "./componentes/layout/HeaderBussola";
import { MTopo } from "./componentes/layout/MTopo";
import { useMidia } from "./componentes/layout/useMidia";
import { CONFIG } from "./config";
import { sugestoesDoComposer } from "./sessao/sugestoes";
import { useSessao } from "./sessao/useSessao";
import { Vistas, type NomeVista } from "./vistas/Vistas";

type Tema = "claro" | "escuro";

const CLIENTE_AUTH = new ClienteAuth();

export function App() {
  // Servido pelo BFF, o modo ao vivo só abre sessão no agente depois do login.
  const auth = useAuth(CONFIG.login, CLIENTE_AUTH);
  const sessao = useSessao(CONFIG.modo, criarTransporte, {
    aoVivoLiberado: auth.fase !== "anonimo" && auth.fase !== "verificando",
    // A conversa lembrada é por persona: trocar de login não herda o chat da outra.
    usuario: auth.persona?.login,
  });
  const { modelo, modo, pronta, bordas } = sessao;
  const pedeLogin = modo === "ao-vivo" && (auth.fase === "anonimo" || auth.fase === "verificando");
  const desktop = useMidia("(min-width: 1024px)", true);
  const [tema, setTema] = useState<Tema>("claro");
  const [painel, setPainel] = useState(false); // Bastidores só quando solicitados: a jornada tem prioridade.
  const [folha, setFolha] = useState(false);
  const [vista, setVista] = useState<NomeVista | null>(null);

  // O modo claro é o padrão da demo; o apresentador alterna na barra.
  const escuro = tema === "escuro";
  const { estado, ocupado } = modelo;
  const jornada = estado.estado_jornada;

  const enviar = (texto: string) => {
    setVista(null);
    sessao.enviar(texto);
  };
  const enviarDaBarra = (texto: string) => {
    setFolha(false);
    enviar(texto);
  };
  const alternarTema = () => setTema(escuro ? "claro" : "escuro");
  const trocarPersona = () => {
    setFolha(false);
    setVista(null);
    void auth.sair().finally(sessao.reiniciar);
  };
  const abrirPlano = () => setVista("meu-plano");
  // Trocar de conversa sai da vista do plano: o plano é o da conversa aberta.
  const abrirConversa = (sessionId: string) => {
    setFolha(false);
    setVista(null);
    sessao.abrirConversa(sessionId);
  };
  const novaConversa = () => {
    setFolha(false);
    setVista(null);
    sessao.novaConversa();
  };

  const barra = (
    <BarraDemo
      estado={estado}
      modo={modo}
      onModo={sessao.trocarModo}
      onEnviar={enviarDaBarra}
      ocupado={ocupado}
      bordas={bordas}
      onBordas={sessao.configurarBordas}
      persona={auth.persona ? { nome: auth.persona.displayName, onTrocar: trocarPersona } : undefined}
      conversas={sessao.conversas}
      conversaAtual={sessao.conversaAtual}
      onConversa={abrirConversa}
      onNovaConversa={novaConversa}
    />
  );

  const principal = pedeLogin ? (
    auth.fase === "verificando" ? null : (
      <TelaLogin cliente={CLIENTE_AUTH} onEntrar={auth.entrar} onModoSimulado={() => sessao.trocarModo("simulado")} compacto={!desktop} />
    )
  ) : vista ? (
    <Vistas vista={vista} modelo={modelo} onVista={setVista} onConversa={() => setVista(null)} onEnviar={enviar} />
  ) : (
    <>
      {desktop ? (
        <StepperJornada atual={jornada} />
      ) : (
        <MTopo atual={jornada} onBastidores={() => setFolha(true)} onMeuPlano={abrirPlano} escuro={escuro} onTema={alternarTema} />
      )}
      <Conversa
        itens={modelo.itens}
        estado={estado}
        ocupado={ocupado}
        lento={modo === "simulado" && bordas.e5}
        onEnviar={enviar}
        onRepetir={sessao.repetir}
        onModoSimulado={modo === "ao-vivo" ? () => sessao.trocarModo("simulado") : undefined}
        vazio={<BoasVindas nome={modo === "ao-vivo" ? auth.persona?.displayName : undefined} onEscolher={enviar} desabilitado={!pronta || ocupado} compacto={!desktop} />}
      />
      <Composer
        sugestoes={modelo.itens.some((item) => item.tipo === "mensagem_cliente") ? sugestoesDoComposer(modelo, modo) : []}
        onEnviar={enviar}
        onParar={sessao.parar}
        ocupado={ocupado}
        desabilitado={!pronta}
      />
    </>
  );

  return (
    <div className={escuro ? "app tokens dark" : "app tokens"} data-estado={(jornada ?? "OBJETIVO").toLowerCase()}>
      <Ambiente />
      <div
        className="layer"
        style={{
          height: "100%",
          boxSizing: "border-box",
          padding: desktop ? 16 : 12,
          display: "flex",
          flexDirection: "column",
          gap: desktop ? 16 : 12,
        }}
      >
        {desktop && (
          <HeaderBussola
            bastidores={painel}
            onBastidores={() => setPainel((v) => !v)}
            escuro={escuro}
            onTema={alternarTema}
            onMeuPlano={abrirPlano}
          />
        )}
        <div style={{ flex: "1 1 auto", minHeight: 0, display: "flex", gap: 16 }}>
          <main style={{ flex: "1 1 auto", minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column", gap: desktop ? 14 : 12 }}>
            {principal}
          </main>
          {desktop && painel && <Bastidores modelo={modelo} variante="painel" onFechar={() => setPainel(false)} apresentador={barra} />}
        </div>
      </div>
      {!desktop && folha && <Bastidores modelo={modelo} variante="folha" onFechar={() => setFolha(false)} apresentador={barra} />}
    </div>
  );
}
