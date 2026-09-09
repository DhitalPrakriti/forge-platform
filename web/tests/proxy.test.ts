import { describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/forge/[...path]/route";
const context = (path: string) => ({
  params: Promise.resolve({ path: path.split("/") }),
});
describe("same-origin backend proxy", () => {
  it("uses the browser Host for loopback origin checking and forwards only context headers", async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response('{"id":"created"}', {
        status: 201,
        headers: { "X-Trace-ID": "trace-1" },
      }),
    );
    vi.stubGlobal("fetch", fetch);
    const request = new NextRequest("http://localhost:3100/api/forge/agents", {
      method: "POST",
      headers: {
        host: "127.0.0.1:3100",
        origin: "http://127.0.0.1:3100",
        "X-Organization-ID": "org-a",
        "Idempotency-Key": "key-1",
        cookie: "private=cookie",
      },
      body: '{"name":"Agent"}',
    });
    const result = await POST(request, context("agents"));
    expect(result.status).toBe(201);
    expect(result.headers.get("X-Trace-ID")).toBe("trace-1");
    const [url, init] = fetch.mock.calls[0];
    expect(url.pathname).toBe("/api/v1/agents");
    expect(init.headers.get("X-Organization-ID")).toBe("org-a");
    expect(init.headers.get("Idempotency-Key")).toBe("key-1");
    expect(init.headers.has("cookie")).toBe(false);
  });
  it("rejects cross-origin mutations before forwarding them", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const result = await POST(
      new NextRequest("http://localhost:3100/api/forge/agents", {
        method: "POST",
        headers: { origin: "https://unrelated.example" },
      }),
      context("agents"),
    );
    expect(result.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("does not forward arbitrary routes", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const result = await GET(
      new NextRequest("http://localhost:3100/api/forge/secrets"),
      context("secrets"),
    );
    expect(result.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("sanitizes upstream connection errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockRejectedValue(
          new Error("internal credential-bearing diagnostics"),
        ),
    );
    const result = await GET(
      new NextRequest("http://localhost:3100/api/forge/health/ready"),
      context("health/ready"),
    );
    expect(result.status).toBe(502);
    expect(await result.text()).not.toContain("credential-bearing");
  });
});

it("forwards reviewer credentials only to approval and resume actions", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(() => Promise.resolve(new Response("{}")));
  vi.stubGlobal("fetch", fetch);
  for (const path of [
    "approvals/11111111-1111-4111-8111-111111111111/approve",
    "runs/11111111-1111-4111-8111-111111111111/resume",
    "agents",
  ]) {
    await POST(
      new NextRequest(`http://localhost:3100/api/forge/${path}`, {
        method: "POST",
        headers: { authorization: "Bearer local-test-credential" },
      }),
      context(path),
    );
    const init = fetch.mock.calls.at(-1)![1];
    expect(init.headers.get("Authorization")).toBe(
      path === "agents" ? null : "Bearer local-test-credential",
    );
  }
});
