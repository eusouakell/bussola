// Login simulado: o apresentador escolhe uma persona (massa de dados
// sintética) e digita a senha padrão de teste. O `id_usuario` fica no BFF.
import { useEffect, useId, useState, type FormEvent } from "react";
import { Icone } from "../componentes/base/Icone";
import { SeloSintetico } from "../componentes/base/SeloSintetico";
import { FalhaAuth, type ClienteAuth, type Persona } from "./clienteAuth";

interface Props {
  cliente: ClienteAuth;
  onEntrar: (login: string, senha: string) => Promise<void>;
  onModoSimulado: () => void;
  compacto?: boolean;
}

type Personas = { fase: "carregando" } | { fase: "ok"; lista: Persona[] } | { fase: "erro"; mensagem: string };

function mensagemDe(erro: unknown): string {
  return erro instanceof FalhaAuth ? erro.message : "Não foi possível entrar. Tente de novo.";
}

export function TelaLogin({ cliente, onEntrar, onModoSimulado, compacto }: Props) {
  const idSenha = useId();
  const idErro = useId();
  const [personas, setPersonas] = useState<Personas>({ fase: "carregando" });
  const [escolhida, setEscolhida] = useState<string | null>(null);
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let vivo = true;
    cliente
      .listarPersonas()
      .then((lista) => {
        if (!vivo) return;
        setPersonas({ fase: "ok", lista });
        setEscolhida((atual) => atual ?? lista[0]?.login ?? null);
      })
      .catch((e: unknown) => {
        if (vivo) setPersonas({ fase: "erro", mensagem: mensagemDe(e) });
      });
    return () => {
      vivo = false;
    };
  }, [cliente, tentativa]);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (!escolhida || !senha || enviando) return;
    setEnviando(true);
    setErro(null);
    try {
      await onEntrar(escolhida, senha);
    } catch (e) {
      setErro(mensagemDe(e));
      setSenha("");
      setEnviando(false);
    }
  };

  return (
    <div
      className="enter"
      style={{
        width: "100%",
        maxWidth: 560,
        margin: "auto",
        padding: compacto ? "24px 4px" : "32px 4px",
        display: "flex",
        flexDirection: "column",
        gap: 20,
        boxSizing: "border-box",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span className="brand-mark lg" aria-hidden="true">
          <Icone nome="bussola" tamanho="lg" />
        </span>
        <SeloSintetico />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <h1 style={{ margin: 0, fontSize: compacto ? 28 : 36, lineHeight: compacto ? "34px" : "42px", fontWeight: 900, letterSpacing: "-.02em" }}>
          Escolha uma persona
        </h1>
        <p style={{ margin: 0, fontSize: 17, lineHeight: "25px", fontWeight: 600, color: "var(--ink-2)" }}>
          Cada persona é uma massa de dados sintética. Entre com a senha padrão de teste da demo.
        </p>
      </div>

      <form onSubmit={(e) => void enviar(e)} style={{ display: "flex", flexDirection: "column", gap: 14 }} aria-describedby={erro ? idErro : undefined}>
        {personas.fase === "carregando" && (
          <p role="status" style={{ margin: 0, fontWeight: 700, color: "var(--ink-2)" }}>
            Carregando personas…
          </p>
        )}
        {personas.fase === "erro" && (
          <div className="glass-card card-pad" role="alert" style={{ gap: 12 }}>
            <div className="note note-err">
              <Icone nome="alerta" />
              <span>{personas.mensagem}</span>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setPersonas({ fase: "carregando" });
                setTentativa((t) => t + 1);
              }}
            >
              <Icone nome="recarregar" />
              Tentar de novo
            </button>
          </div>
        )}
        {personas.fase === "ok" && (
          <fieldset style={{ margin: 0, padding: 0, border: 0, display: "flex", flexDirection: "column", gap: 10 }}>
            <legend className="sr-only">Persona</legend>
            {personas.lista.length === 0 && (
              <p style={{ margin: 0, fontWeight: 700, color: "var(--ink-2)" }}>Nenhuma persona disponível no momento.</p>
            )}
            {personas.lista.map((p) => {
              const marcada = escolhida === p.login;
              return (
                <label
                  key={p.login}
                  className="glass-card"
                  style={{
                    cursor: "pointer",
                    padding: "14px 18px",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 14,
                    borderRadius: 20,
                    boxShadow: marcada ? "0 0 0 3px var(--accent-soft)" : undefined,
                    borderColor: marcada ? "var(--accent)" : undefined,
                  }}
                >
                  <input
                    type="radio"
                    name="persona"
                    value={p.login}
                    checked={marcada}
                    onChange={() => setEscolhida(p.login)}
                    style={{ width: 18, height: 18, marginTop: 3, accentColor: "var(--accent)" }}
                  />
                  <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{ fontSize: 17, fontWeight: 800 }}>{p.displayName}</span>
                    <span style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-2)" }}>{p.summary}</span>
                  </span>
                </label>
              );
            })}
          </fieldset>
        )}

        <label htmlFor={idSenha} style={{ fontSize: 14, fontWeight: 800 }}>
          Senha padrão de teste
        </label>
        <div className="field">
          <Icone nome="cadeado" tamanho="sm" />
          <input
            id={idSenha}
            type="password"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            maxLength={128}
            required
          />
        </div>

        {erro && (
          <div id={idErro} className="note note-err" role="alert">
            <Icone nome="alerta" />
            <span>{erro}</span>
          </div>
        )}

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button type="submit" className="btn btn-primary" disabled={!escolhida || !senha || enviando}>
            {enviando ? "Entrando…" : "Entrar"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={onModoSimulado}>
            <Icone nome="frasco" />
            Usar modo simulado
          </button>
        </div>
      </form>
    </div>
  );
}
