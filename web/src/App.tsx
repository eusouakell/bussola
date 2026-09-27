// Casca da aplicação (Main.dc.html no desktop, M*.dc.html abaixo de 1024 px):
// conversa, stepper, composer, Bastidores com a barra do apresentador e as
// vistas do plano (P1–P5), sem roteador.
import { useState } from "react";
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
import { criarTransporte, useSessao } from "./sessao/useSessao";
import { Vistas, type NomeVista } from "./vistas/Vistas";

type Tema = "claro" | "escuro";

const CLIENTE_AUTH = new ClienteAuth();

export function App() {
  // Servido pelo BFF, o modo ao vivo só abre sessão no agente depois do login.
  const auth = useAuth(CONFIG.login, CLIENTE_AUTH);
  const sessao = useSessao(CONFIG.modo, criarTransporte, { aoVivoLiberado: auth.fase !== "anonimo" && auth.fase !== "verificando" });
  const { modelo, modo, pronta, bordas } = sessao;
  const pedeLogin = modo === "ao-vivo" && (auth.fase === "anonimo" || auth.fase === "verificando");
  const desktop = useMidia("(min-width: 1024px)", true);
  const sistemaEscuro = useMidia("(prefers-color-scheme: dark)", false);
  const [tema, setTema] = useState<Tema | null>(null);
  const [painel, setPainel] = useState(true);
  const [folha, setFolha] = useState(false);
  const [vista, setVista] = useState<NomeVista | null>(null);

  const escuro = tema ? tema === "escuro" : sistemaEscuro;
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
        sugestoes={sugestoesDoComposer(modelo)}
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
