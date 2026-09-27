// Origem de contas no BigQuery pela API REST `tabledata.list`: lê a tabela
// sem job e sem SQL (basta `bigquery.dataViewer` no dataset). O esquema vem
// de `tables.get`, para mapear as colunas pelo nome.
import { parseUserAccount, type UserAccount } from "../../domain/userAccount.ts";
import type { AccessTokenProvider } from "../gcp/credentials.ts";
import type { UserSource } from "./userSource.ts";

type Fetch = typeof fetch;

export interface BigQueryTable {
  project: string;
  dataset: string;
  table: string;
}

export interface BigQueryUserSourceOptions extends BigQueryTable {
  credentials: AccessTokenProvider;
  fetch?: Fetch;
  pageSize?: number;
  maxRows?: number;
  onInvalidRows?: (count: number) => void;
}

interface TableSchema {
  schema?: { fields?: { name?: unknown; type?: unknown }[] };
}

interface TableData {
  rows?: { f?: { v?: unknown }[] }[];
  pageToken?: unknown;
}

const PROJECT_ID = /^[a-z][a-z0-9-]{4,28}[a-z0-9]$/;
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]{0,1023}$/;
const API = "https://bigquery.googleapis.com/bigquery/v2";

export class BigQueryError extends Error {
  constructor(reason: string) {
    super(`BigQuery: ${reason}`);
    this.name = "BigQueryError";
  }
}

function cell(value: unknown, type: string): unknown {
  // A REST devolve tudo como texto; só BOOL precisa de conversão aqui.
  if (type === "BOOL" || type === "BOOLEAN") return value === "true" ? true : value === "false" ? false : value;
  return value;
}

export class BigQueryUserSource implements UserSource {
  private readonly options: Required<Omit<BigQueryUserSourceOptions, "onInvalidRows">> &
    Pick<BigQueryUserSourceOptions, "onInvalidRows">;

  constructor(options: BigQueryUserSourceOptions) {
    if (!PROJECT_ID.test(options.project)) throw new BigQueryError("projeto inválido");
    if (!IDENTIFIER.test(options.dataset) || !IDENTIFIER.test(options.table)) {
      throw new BigQueryError("dataset ou tabela inválidos");
    }
    this.options = { fetch, pageSize: 1000, maxRows: 20_000, ...options };
  }

  async loadAll(): Promise<UserAccount[]> {
    const { project, dataset, table, pageSize, maxRows } = this.options;
    const base = `${API}/projects/${project}/datasets/${dataset}/tables/${table}`;
    const fields = ((await this.get<TableSchema>(base)).schema?.fields ?? []).map((field) => ({
      name: String(field.name),
      type: String(field.type).toUpperCase(),
    }));
    if (!fields.length) throw new BigQueryError("tabela sem esquema");

    const accounts: UserAccount[] = [];
    let invalid = 0;
    let read = 0;
    let pageToken: string | undefined;
    do {
      const query = new URLSearchParams({ maxResults: String(pageSize) });
      if (pageToken) query.set("pageToken", pageToken);
      const page = await this.get<TableData>(`${base}/data?${query}`);
      for (const row of page.rows ?? []) {
        read += 1;
        const record = Object.fromEntries(fields.map((field, i) => [field.name, cell(row.f?.[i]?.v, field.type)]));
        try {
          accounts.push(parseUserAccount(record));
        } catch {
          invalid += 1;
        }
      }
      if (read > maxRows) throw new BigQueryError(`mais de ${maxRows} linhas em users`);
      pageToken = typeof page.pageToken === "string" && page.pageToken ? page.pageToken : undefined;
    } while (pageToken);

    if (invalid) this.options.onInvalidRows?.(invalid);
    return accounts;
  }

  private async get<T>(url: string): Promise<T> {
    const token = await this.options.credentials.accessToken();
    let response: Response;
    try {
      response = await this.options.fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(15_000),
      });
    } catch {
      throw new BigQueryError("sem resposta");
    }
    if (!response.ok) throw new BigQueryError(`HTTP ${response.status}`);
    return (await response.json()) as T;
  }
}
