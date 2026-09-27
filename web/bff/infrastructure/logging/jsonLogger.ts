// Log JSON em stdout, compatível com Cloud Logging (contratos §9). Só os
// campos da lista de permitidos saem; o resto é descartado mesmo que chegue
// por engano.
import type { LogFields, Logger } from "../../application/ports/logger.ts";

const ALLOWED: ReadonlySet<string> = new Set([
  "evento",
  "session_id",
  "id_usuario",
  "latencia_ms",
  "erro_codigo",
  "excecao",
]);

export const SERVICE_NAME = "bussola-bff";

export function jsonLogger(write: (line: string) => void = (line) => process.stdout.write(line)): Logger {
  const emit = (severity: string, message: string, fields: LogFields = {}) => {
    const allowed = Object.fromEntries(Object.entries(fields).filter(([key]) => ALLOWED.has(key)));
    const entry = { severity, message, timestamp: new Date().toISOString(), servico: SERVICE_NAME, ...allowed };
    write(`${JSON.stringify(entry)}\n`);
  };
  return {
    info: (message, fields) => emit("INFO", message, fields),
    warn: (message, fields) => emit("WARNING", message, fields),
    error: (message, fields) => emit("ERROR", message, fields),
  };
}

export const silentLogger: Logger = { info: () => {}, warn: () => {}, error: () => {} };
