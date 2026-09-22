import { NextRequest, NextResponse } from "next/server";

// A fixed upstream keeps browser traffic same-origin. This is local context, not authentication.
export const runtime = "nodejs";
const uuid = "[0-9a-fA-F-]{36}";
const routes: Record<string, RegExp[]> = {
  GET: [
    new RegExp(`^agent-versions/${uuid}/runs$`),
    /^knowledge\/documents$/,
    new RegExp(`^knowledge/documents/${uuid}$`),
    /^mcp\/servers$/,
    /^mcp\/servers\/[a-z][a-z0-9_-]{0,31}\/tools$/,
    /^policies$/,
    /^approvals$/,
    new RegExp(`^approvals/${uuid}$`),
    /^tools$/,
    new RegExp(`^tools/${uuid}$`),
    /^health\/ready$/,
    /^models\/health$/,
    /^organizations\/current$/,
    /^agents$/,
    new RegExp(`^agents/${uuid}(/versions(/${uuid})?)?$`),
    new RegExp(`^runs/${uuid}(/events|/model-calls|/tool-calls)?$`),
  ],
  POST: [
    /^knowledge\/(documents|search)$/,
    /^mcp\/tools$/,
    /^policies$/,
    new RegExp(`^approvals/${uuid}/(approve|deny)$`),
    new RegExp(`^runs/${uuid}/resume$`),
    /^tools$/,
    /^organizations$/,
    /^agents$/,
    new RegExp(`^agents/${uuid}/versions$`),
    new RegExp(`^agent-versions/${uuid}/archive$`),
    /^runs$/,
    new RegExp(`^runs/${uuid}/(cancel|retry)$`),
  ],
  PATCH: [new RegExp(`^tools/${uuid}$`)],
};
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const path = (await context.params).path.join("/");
  if (!routes[request.method]?.some((route) => route.test(path))) {
    return NextResponse.json(
      {
        error: {
          code: "ROUTE_NOT_AVAILABLE",
          message: "This action is not available in the local console.",
        },
      },
      { status: 404 },
    );
  }
  // Reject browser cross-origin mutations; org headers must never become public authentication.
  const origin = request.headers.get("origin");
  // Next's internal URL can use localhost even when the browser uses 127.0.0.1.
  const browserUrl = new URL(request.url);
  browserUrl.host = request.headers.get("host") || browserUrl.host;
  if (request.method !== "GET" && origin && origin !== browserUrl.origin) {
    return NextResponse.json(
      {
        error: {
          code: "ORIGIN_REJECTED",
          message: "Use the local console to submit this request.",
        },
      },
      { status: 403 },
    );
  }
  const headers = new Headers({ "Content-Type": "application/json" });
  for (const name of ["X-Organization-ID", "Idempotency-Key"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (/^(approvals\/.+\/(approve|deny)|runs\/.+\/resume)$/.test(path)) {
    const auth = request.headers.get("authorization");
    if (auth) headers.set("Authorization", auth);
  }
  try {
    const upstream = new URL(
      `/api/v1/${path}`,
      process.env.FORGE_API_URL || "http://127.0.0.1:8000",
    );
    upstream.search = request.nextUrl.search;
    let body: string | undefined;
    if (request.method !== "GET") {
      if (path === "knowledge/documents" && request.body) {
        const reader = request.body.getReader();
        const chunks: Uint8Array[] = [];
        let size = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > 4_010_000) {
            await reader.cancel();
            return NextResponse.json(
              {
                error: {
                  code: "DOCUMENT_TOO_LARGE",
                  message: "Upload must be at most 3 MB.",
                },
              },
              { status: 413 },
            );
          }
          chunks.push(value);
        }
        body = Buffer.concat(chunks).toString("utf8");
      } else {
        body = await request.text();
      }
    }
    const result = await fetch(upstream, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(310_000),
    });
    return new Response(await result.text(), {
      status: result.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "X-Trace-ID": result.headers.get("X-Trace-ID") || "",
      },
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "BACKEND_UNAVAILABLE",
          message:
            "Could not reach the backend. Check that the API and PostgreSQL are running. A submitted run may still have been accepted; use Retry same request.",
        },
      },
      { status: 502 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH };
