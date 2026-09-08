import { describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/forge";
import { request } from "@/lib/api/client";
describe("API boundary", () => {
  it("automatically scopes agent creation without changing the JSON contract", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ id: "agent" }), { status: 201 }),
      );
    vi.stubGlobal("fetch", fetch);
    await api.createAgent("org-a", {
      name: "Support",
      slug: "support",
      description: "",
    });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/forge/agents");
    expect(init.headers.get("X-Organization-ID")).toBe("org-a");
    expect(JSON.parse(init.body)).toEqual({
      name: "Support",
      slug: "support",
      description: "",
    });
  });
  it("carries the same idempotency key when the caller retries", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network"))
      .mockResolvedValueOnce(new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    const body = { agent_version_id: "v", input: { message: "hello" } };
    await expect(
      api.createRun("org-a", body, "retry-key"),
    ).rejects.toMatchObject({ code: "NETWORK_ERROR" });
    await api.createRun("org-a", body, "retry-key");
    for (const [, init] of fetch.mock.calls)
      expect(init.headers.get("Idempotency-Key")).toBe("retry-key");
  });
  it("preserves backend error code and trace ID for troubleshooting", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "AGENT_SLUG_CONFLICT",
              message: "Slug already exists.",
              trace_id: "trace-123",
            },
          }),
          { status: 409 },
        ),
      ),
    );
    await expect(request("/agents")).rejects.toMatchObject({
      message: "Slug already exists.",
      code: "AGENT_SLUG_CONFLICT",
      status: 409,
      traceId: "trace-123",
    });
  });
  it("does not show raw non-JSON upstream error pages", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("private upstream diagnostics", { status: 502 }),
        ),
    );
    await expect(request("/agents")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
      message: "The server returned an unreadable response.",
    });
  });
});
