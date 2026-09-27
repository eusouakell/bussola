// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { ManualClock } from "../../test/helpers.ts";
import { CredentialsError, GcloudAdcCredentials, MetadataServerCredentials } from "./credentials.ts";

describe("MetadataServerCredentials", () => {
  it("busca o access token com Metadata-Flavor e usa o cache até perto do fim", async () => {
    const clock = new ManualClock();
    const fetch = vi.fn(async () => Response.json({ access_token: "a1", expires_in: 3600 }));
    const credentials = new MetadataServerCredentials({ fetch, now: clock.now });

    expect(await credentials.accessToken()).toBe("a1");
    expect(await credentials.accessToken()).toBe("a1");
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/metadata\.google\.internal\/.*\/token$/);
    expect(new Headers(init.headers).get("Metadata-Flavor")).toBe("Google");

    clock.advance(3600_000 - 59_000);
    await credentials.accessToken();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("pede ID token por audience", async () => {
    const fetch = vi.fn(async () => new Response("jwt\n"));
    const credentials = new MetadataServerCredentials({ fetch });
    expect(await credentials.idToken("https://bussola-agent.example.run.app")).toBe("jwt");
    const url = new URL(String((fetch.mock.calls[0] as unknown[])[0]));
    expect(url.searchParams.get("audience")).toBe("https://bussola-agent.example.run.app");
    expect(url.searchParams.get("format")).toBe("full");
  });

  it("metadata server fora do ar vira CredentialsError", async () => {
    const credentials = new MetadataServerCredentials({ fetch: vi.fn(async () => new Response("", { status: 500 })) });
    await expect(credentials.accessToken()).rejects.toThrow(CredentialsError);
  });
});

describe("GcloudAdcCredentials", () => {
  it("usa o gcloud do ADC e guarda o token por alguns minutos", async () => {
    const clock = new ManualClock();
    const run = vi.fn(async () => "ya29.token\n");
    const credentials = new GcloudAdcCredentials({ run, now: clock.now });

    expect(await credentials.accessToken()).toBe("ya29.token");
    await credentials.accessToken();
    expect(run).toHaveBeenCalledTimes(1);
    expect(run).toHaveBeenCalledWith("gcloud", ["auth", "application-default", "print-access-token"]);
    clock.advance(5 * 60_000 + 1);
    await credentials.accessToken();
    expect(run).toHaveBeenCalledTimes(2);
  });

  it("sem ADC, orienta o login sem repassar a saída do gcloud", async () => {
    const credentials = new GcloudAdcCredentials({ run: vi.fn(async () => Promise.reject(new Error("detalhe interno"))) });
    await expect(credentials.accessToken()).rejects.toThrow(/application-default login/);
  });
});
