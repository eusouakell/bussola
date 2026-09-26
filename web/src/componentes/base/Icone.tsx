// Ícones de traço do protótipo (docs/design/canvas): viewBox 24×24, `class="i"`.
import type { CSSProperties, ReactNode } from "react";

const DB = (
  <>
    <ellipse cx="12" cy="6" rx="7" ry="3" />
    <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
    <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
  </>
);

const ICONES = {
  bussola: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M15.5 8.5l-2 5-5 2 2-5z" />
    </>
  ),
  voltar: <path d="M15 5l-7 7 7 7" />,
  painel: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M15 4v16" />
    </>
  ),
  frasco: <path d="M9 3h6M10 3v6L5 19a1.5 1.5 0 0 0 1.3 2h11.4a1.5 1.5 0 0 0 1.3-2L14 9V3" />,
  casa: (
    <>
      <path d="M3 11l9-7 9 7" />
      <path d="M5 10v10h14V10" />
      <path d="M10 20v-5h4v5" />
    </>
  ),
  aviao: <path d="M2 16l20-8-3 9-6-3-3 5-1-5z" />,
  capelo: (
    <>
      <path d="M2 9l10-5 10 5-10 5z" />
      <path d="M6 11v5c3 2 9 2 12 0v-5" />
    </>
  ),
  lista: (
    <>
      <path d="M4 6h16M4 12h10M4 18h6" />
      <path d="M16 16l2 2 4-4" />
    </>
  ),
  enviar: <path d="M5 12h14M13 6l6 6-6 6" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  x: <path d="M6 6l12 12M18 6L6 18" />,
  alerta: (
    <>
      <path d="M12 4l9 16H3z" />
      <path d="M12 10v4M12 17h.01" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
  db: DB,
  escudo: <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />,
  cadeado: (
    <>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </>
  ),
  calendario: (
    <>
      <rect x="4" y="5" width="16" height="15" rx="2" />
      <path d="M4 10h16M9 3v4M15 3v4" />
    </>
  ),
  estrela: <path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z" />,
  avancar: <path d="M6 6l6 6-6 6M13 6l6 6-6 6" />,
  recarregar: (
    <>
      <path d="M20 11a8 8 0 1 0-2.3 5.7" />
      <path d="M20 5v6h-6" />
    </>
  ),
  chevronBaixo: <path d="M6 9l6 6 6-6" />,
  chevronDireita: <path d="M9 6l6 6-6 6" />,
  diag: <path d="M3 12h4l2-6 4 12 2-6h6" />,
  sim: (
    <>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="10" cy="17" r="2" />
    </>
  ),
  rec: (
    <>
      <path d="M12 3v18" />
      <path d="M5 6h11l3 3-3 3H5z" />
    </>
  ),
  parar: <rect x="7" y="7" width="10" height="10" rx="2" />,
  lua: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />,
  sol: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  conversa: <path d="M4 5h16v11H9l-5 4z" />,
  alvo: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" />
    </>
  ),
  trilha: <path d="M4 19h4v-5h4V9h4V5h4" />,
  grafico: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  sino: (
    <>
      <path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z" />
      <path d="M10 21h4" />
    </>
  ),
  raio: <path d="M13 2L4 14h7l-1 8 9-12h-7z" />,
} satisfies Record<string, ReactNode>;

export type NomeIcone = keyof typeof ICONES;

interface Props {
  nome: NomeIcone;
  tamanho?: "sm" | "lg" | "xl";
  traco?: number;
  estilo?: CSSProperties;
  /** Rótulo acessível; sem rótulo, o ícone é decorativo. */
  rotulo?: string;
  className?: string;
}

export function Icone({ nome, tamanho, traco, estilo, rotulo, className }: Props) {
  const classes = ["i", tamanho ? `i-${tamanho}` : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <svg
      className={classes}
      viewBox="0 0 24 24"
      style={traco ? { strokeWidth: traco, ...estilo } : estilo}
      aria-hidden={rotulo ? undefined : true}
      aria-label={rotulo}
      role={rotulo ? "img" : undefined}
    >
      {ICONES[nome]}
    </svg>
  );
}
