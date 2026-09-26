import type { ReactNode } from "react";
import { Icone, type NomeIcone } from "./Icone";

interface Props {
  children: ReactNode;
  icone?: NomeIcone;
  centralizado?: boolean;
}

export function Disclaimer({ children, icone = "frasco", centralizado }: Props) {
  return (
    <p className="disclaimer" style={{ margin: 0, justifyContent: centralizado ? "center" : undefined }}>
      <Icone nome={icone} tamanho="sm" />
      <span>{children}</span>
    </p>
  );
}

export const DISCLAIMER_SIMULACAO = "Simulação com dados sintéticos. Não é oferta nem garantia de crédito.";
