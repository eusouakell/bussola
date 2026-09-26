import { Icone } from "./Icone";

interface Props {
  compacto?: boolean;
}

/** Selo fixo: todos os dados da demonstração são sintéticos. */
export function SeloSintetico({ compacto }: Props) {
  return (
    <span className={compacto ? "selo sm" : "selo"}>
      <Icone nome="frasco" tamanho="sm" />
      {compacto ? "Dados sintéticos" : "Dados sintéticos · ambiente de demonstração"}
    </span>
  );
}
