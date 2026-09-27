// Gera o AUTH_PASSWORD_HASH da senha padrão de teste. A senha vem do stdin
// (sem eco no terminal) e nunca aparece na linha de comando nem no histórico.
//   npm run -s hash-password
//   printf '%s' "$SENHA" | npm run -s hash-password
import { hashPassword, MAX_PASSWORD_LENGTH } from "../infrastructure/auth/scryptPasswordVerifier.ts";

async function readHidden(): Promise<string> {
  const stdin = process.stdin;
  if (!stdin.isTTY) {
    let data = "";
    for await (const chunk of stdin) data += String(chunk);
    return data.replace(/\r?\n$/, "");
  }
  process.stderr.write("Senha padrão de teste: ");
  stdin.setRawMode(true);
  stdin.setEncoding("utf-8");
  return new Promise((resolve, reject) => {
    let value = "";
    const onData = (key: string) => {
      for (const char of key) {
        if (char === "\u0003") {
          stdin.setRawMode(false);
          reject(new Error("cancelado"));
          return;
        }
        if (char === "\r" || char === "\n") {
          stdin.setRawMode(false);
          stdin.off("data", onData);
          stdin.pause();
          process.stderr.write("\n");
          resolve(value);
          return;
        }
        value = char === "\u007f" ? value.slice(0, -1) : value + char;
      }
    };
    stdin.on("data", onData);
  });
}

const password = await readHidden();
if (password.length < 8 || password.length > MAX_PASSWORD_LENGTH) {
  process.stderr.write(`A senha deve ter de 8 a ${MAX_PASSWORD_LENGTH} caracteres.\n`);
  process.exit(1);
}
process.stdout.write(`${await hashPassword(password)}\n`);
