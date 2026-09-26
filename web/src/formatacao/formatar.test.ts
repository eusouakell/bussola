import { describe, expect, it } from "vitest";
import {
  brl,
  dataHora,
  fracaoPercentual,
  hora,
  horaSegundos,
  mascararArgs,
  mascararId,
  mesAbrev,
  meses,
  mesExtenso,
  percentual,
  periodo,
} from "./formatar";

// Intl usa espaço não separável entre "R$" e o valor.
const sp = (s: string) => s.replace(/\u00a0/g, " ");

describe("formatar", () => {
  it("formata BRL com 2 casas, sem arredondar a mais", () => {
    expect(sp(brl(1681.15))).toBe("R$ 1.681,15");
    expect(sp(brl(-796.62))).toBe("-R$ 796,62");
    expect(sp(brl(30000))).toBe("R$ 30.000,00");
    expect(brl(undefined)).toBe("—");
  });

  it("formata percentuais", () => {
    expect(percentual(35.35)).toBe("35,35%");
    expect(fracaoPercentual(0.8)).toBe("80%");
  });

  it("formata meses e períodos", () => {
    expect(mesAbrev(202507)).toBe("jul/2025");
    expect(mesExtenso(202508)).toBe("agosto de 2025");
    expect(periodo({ inicio: 202501, fim: 202506 })).toBe("jan–jun/2025");
    expect(periodo({ inicio: 202507, fim: 202507 })).toBe("jul/2025");
    expect(periodo({ inicio: 202412, fim: 202501 })).toBe("dez/2024–jan/2025");
    expect(meses(18)).toBe("18 meses");
    expect(meses(1)).toBe("1 mês");
  });

  it("formata data e hora no fuso de São Paulo", () => {
    const ts = Date.parse("2026-09-26T14:32:05-03:00") / 1000;
    expect(dataHora(ts)).toBe("26/09/2026 14:32");
    expect(hora("2026-09-26T14:32:05-03:00")).toBe("14:32");
    expect(horaSegundos(ts)).toBe("14:32:05");
  });

  it("mascara identificadores", () => {
    expect(mascararId("36a21505-d6d4-42d3-b319-d51a133c7269")).toBe("36a2…7269");
    expect(mascararArgs({ id_usuario: "36a21505-d6d4-42d3-b319-d51a133c7269", ate_anomes: 202506 })).toEqual({
      id_usuario: "36a2…7269",
      ate_anomes: 202506,
    });
  });
});
