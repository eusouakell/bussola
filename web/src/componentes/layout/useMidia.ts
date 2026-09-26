// Media query como estado externo (sem setState em effect).
import { useCallback, useSyncExternalStore } from "react";

export function useMidia(consulta: string, padrao: boolean): boolean {
  const assinar = useCallback(
    (avisar: () => void) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const lista = window.matchMedia(consulta);
      lista.addEventListener("change", avisar);
      return () => lista.removeEventListener("change", avisar);
    },
    [consulta],
  );
  const ler = () => (typeof window === "undefined" || !window.matchMedia ? padrao : window.matchMedia(consulta).matches);
  return useSyncExternalStore(assinar, ler, () => padrao);
}
