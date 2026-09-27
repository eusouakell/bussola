// @vitest-environment node
import { randomUUID } from "node:crypto";
import { describe, expect, it, vi } from "vitest";
import { BigQueryError, BigQueryUserSource } from "./bigQueryUserSource.ts";

const TABLE = { project: "projeto-teste", dataset: "bussola_dados", table: "users" };
const credentials = { accessToken: vi.fn(async () => "token-de-teste") };
const SCHEMA = {
  schema: {
    fields: [
      { name: "login", type: "STRING" },
      { name: "id_usuario", type: "STRING" },
      { name: "display_name", type: "STRING" },
      { name: "summary", type: "STRING" },
      { name: "featured", type: "BOOLEAN" },
    ],
  },
};

function row(login: string, featured = "true", id: string = randomUUID()) {
  return { f: [{ v: login }, { v: id }, { v: `Persona ${login}` }, { v: "Resumo." }, { v: featured }] };
}

function fakeFetch(pages: unknown[]) {
  return vi.fn<(url: string | URL | Request, init?: RequestInit) => Promise<Response>>(async (url) => {
    const href = String(url);
    const body = href.includes("/data?") ? pages.shift() : SCHEMA;
    return Response.json(body);
  });
}

describe("BigQueryUserSource", () => {
  it("lê o esquema e todas as páginas pelo tabledata.list, sem SQL", async () => {
    const fetch = fakeFetch([
      { rows: [row("fernando")], pageToken: "p2" },
      { rows: [row("cliente-0a1b2c3d", "false")] },
    ]);
    const source = new BigQueryUserSource({ ...TABLE, credentials, fetch });

    const accounts = await source.loadAll();

    expect(accounts.map((a) => [a.login, a.featured])).toEqual([
      ["fernando", true],
      ["cliente-0a1b2c3d", false],
    ]);
    const urls = fetch.mock.calls.map(([url]) => String(url));
    expect(urls[0]).toBe("https://bigquery.googleapis.com/bigquery/v2/projects/projeto-teste/datasets/bussola_dados/tables/users");
    expect(urls[1]).toContain("/tables/users/data?maxResults=1000");
    expect(urls[2]).toContain("pageToken=p2");
    expect(urls.join(" ")).not.toMatch(/queries|jobs|SELECT/i);
    const init = fetch.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer token-de-teste");
  });

  it("ignora linhas inválidas e avisa a contagem", async () => {
    const onInvalidRows = vi.fn();
    const fetch = fakeFetch([{ rows: [row("fernando"), row("Login Ruim"), row("outra", "true", "nao-e-uuid")] }]);
    const source = new BigQueryUserSource({ ...TABLE, credentials, fetch, onInvalidRows });

    expect((await source.loadAll()).map((a) => a.login)).toEqual(["fernando"]);
    expect(onInvalidRows).toHaveBeenCalledWith(2);
  });

  it("falha com HTTP de erro sem expor detalhes", async () => {
    const fetch = vi.fn(async () => new Response("Access Denied: projeto-teste:bussola_dados", { status: 403 }));
    const source = new BigQueryUserSource({ ...TABLE, credentials, fetch });
    await expect(source.loadAll()).rejects.toThrow(new BigQueryError("HTTP 403"));
  });

  it("para se a tabela passar do máximo de linhas", async () => {
    const fetch = fakeFetch([{ rows: [row("a1"), row("b1")], pageToken: "p2" }]);
    const source = new BigQueryUserSource({ ...TABLE, credentials, fetch, maxRows: 1 });
    await expect(source.loadAll()).rejects.toThrow("mais de 1 linhas");
  });

  it.each([
    { project: "Projeto Ruim" },
    { dataset: "bussola_dados`; DROP" },
    { table: "users/../x" },
  ])("recusa identificador inválido %j", (override) => {
    expect(() => new BigQueryUserSource({ ...TABLE, ...override, credentials })).toThrow(BigQueryError);
  });
});
