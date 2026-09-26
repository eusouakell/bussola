// Composer (FR-006): sugestões em chips, campo de mensagem, enviar e parar.
import { useState, type FormEvent } from "react";
import { Icone } from "../base/Icone";

interface Props {
  sugestoes: string[];
  onEnviar: (texto: string) => void;
  onParar: () => void;
  ocupado: boolean;
  /** Sessão ainda sem state (ou em falha): nada a enviar. */
  desabilitado?: boolean;
  placeholder?: string;
}

export function Composer({ sugestoes, onEnviar, onParar, ocupado, desabilitado, placeholder }: Props) {
  const [texto, setTexto] = useState("");
  const bloqueado = ocupado || Boolean(desabilitado);

  function enviar(evento: FormEvent) {
    evento.preventDefault();
    const limpo = texto.trim();
    if (!limpo || bloqueado) return;
    onEnviar(limpo);
    setTexto("");
  }

  return (
    <div style={{ width: "100%", maxWidth: 760, margin: "0 auto", display: "flex", flexDirection: "column", gap: 10, flexShrink: 0 }}>
      {sugestoes.length > 0 && (
        <div
          role="group"
          aria-label="Sugestões"
          style={{ display: "flex", gap: 8, overflowX: "auto", scrollbarWidth: "none", padding: "2px 2px 4px" }}
        >
          {sugestoes.map((s) => (
            <button key={s} type="button" className="suggest glass-chrome" disabled={bloqueado} onClick={() => onEnviar(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
      <form className="glass-chrome composer" onSubmit={enviar}>
        <label htmlFor="mensagem" className="sr-only">
          Mensagem para a Bússola
        </label>
        <input
          id="mensagem"
          type="text"
          autoComplete="off"
          value={texto}
          maxLength={500}
          placeholder={placeholder ?? "Escreva para a Bússola…"}
          onChange={(e) => setTexto(e.target.value)}
          disabled={Boolean(desabilitado)}
        />
        {ocupado ? (
          <button type="button" className="send" aria-label="Parar resposta" onClick={onParar} style={{ background: "var(--ink)" }}>
            <Icone nome="parar" estilo={{ fill: "currentColor" }} />
          </button>
        ) : (
          <button type="submit" className="send" aria-label="Enviar" disabled={bloqueado || !texto.trim()}>
            <Icone nome="enviar" traco={2.4} />
          </button>
        )}
      </form>
    </div>
  );
}
