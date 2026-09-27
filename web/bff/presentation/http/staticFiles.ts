// Arquivos do build do Vite (`web/dist`) com fallback de SPA para o
// `index.html`. Caminho fora da raiz não é servido.
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import type { ServerResponse } from "node:http";
import { extname, resolve, sep } from "node:path";

const CONTENT_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".json": "application/json; charset=utf-8",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".txt": "text/plain; charset=utf-8",
};

async function fileSize(path: string): Promise<number | null> {
  try {
    const info = await stat(path);
    return info.isFile() ? info.size : null;
  } catch {
    return null;
  }
}

/** Serve o arquivo e devolve `true`, ou `false` se não houver o que servir. */
export async function serveStatic(root: string, pathname: string, res: ServerResponse, head: boolean): Promise<boolean> {
  const base = resolve(root);
  if (pathname.includes("\0")) return false;
  let path = resolve(base, `.${pathname}`);
  if (path !== base && !path.startsWith(base + sep)) return false;
  let size = path === base ? null : await fileSize(path);
  if (size === null) {
    // Rota da SPA (sem extensão): entrega o index.html.
    if (extname(pathname)) return false;
    path = resolve(base, "index.html");
    size = await fileSize(path);
    if (size === null) return false;
  }
  const immutable = path.startsWith(resolve(base, "assets") + sep);
  res.writeHead(200, {
    "Content-Type": CONTENT_TYPES[extname(path)] ?? "application/octet-stream",
    "Content-Length": size,
    "Cache-Control": immutable ? "public, max-age=31536000, immutable" : "no-cache",
  });
  if (head) {
    res.end();
    return true;
  }
  await new Promise<void>((done) => {
    createReadStream(path).on("error", () => res.destroy()).on("close", done).pipe(res);
  });
  return true;
}
