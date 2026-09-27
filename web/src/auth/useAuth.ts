// Estado do login simulado no BFF. Desligado (`ativo = false`), o front roda
// como antes: simulado ou ao vivo direto no ADK pelo proxy do Vite.
import { useCallback, useEffect, useState } from "react";
import { ClienteAuth, type Persona } from "./clienteAuth";

export type FaseAuth = "desligado" | "verificando" | "anonimo" | "logado";

export interface Auth {
  fase: FaseAuth;
  persona: Persona | null;
  /** Lança `FalhaAuth` com a mensagem do BFF (senha errada, muitas tentativas...). */
  entrar: (login: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
}

const CLIENTE_PADRAO = new ClienteAuth();

export function useAuth(ativo: boolean, cliente: ClienteAuth = CLIENTE_PADRAO): Auth {
  const [verificado, setVerificado] = useState(false);
  const [persona, setPersona] = useState<Persona | null>(null);

  useEffect(() => {
    if (!ativo) return;
    let vivo = true;
    cliente
      .sessaoAtual()
      .catch(() => null)
      .then((atual) => {
        if (!vivo) return;
        setPersona(atual);
        setVerificado(true);
      });
    return () => {
      vivo = false;
    };
  }, [ativo, cliente]);

  const entrar = useCallback(
    async (login: string, senha: string) => {
      setPersona(await cliente.entrar(login, senha));
    },
    [cliente],
  );

  const sair = useCallback(async () => {
    try {
      await cliente.sair();
    } finally {
      setPersona(null);
    }
  }, [cliente]);

  const fase: FaseAuth = !ativo ? "desligado" : !verificado ? "verificando" : persona ? "logado" : "anonimo";
  return { fase, persona: ativo ? persona : null, entrar, sair };
}
