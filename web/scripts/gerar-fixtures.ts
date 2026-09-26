// Gera web/fixtures/ (npm run fixtures). Não editar os JSON à mão.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { DIR_WEB_FIXTURES, montarGoldens, serializar } from "./fixtures-lib";

mkdirSync(DIR_WEB_FIXTURES, { recursive: true });

const goldens = join(DIR_WEB_FIXTURES, "goldens.json");
writeFileSync(goldens, serializar(montarGoldens()));
console.log(`gravado ${goldens}`);

// O roteiro usa os goldens recém-gravados: import dinâmico depois da escrita.
const { gerarRoteiro } = await import("../src/simulado/roteiro");
const roteiro = join(DIR_WEB_FIXTURES, "roteiro-demo.json");
writeFileSync(roteiro, serializar(gerarRoteiro()));
console.log(`gravado ${roteiro}`);
