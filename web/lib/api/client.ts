export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
    public traceId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export async function request<T>(
  path: string,
  organizationId?: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (organizationId) headers.set("X-Organization-ID", organizationId);
  if (init.body) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`/api/forge${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Could not reach FORGE. Check the local servers and try again.",
      "NETWORK_ERROR",
      0,
    );
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(
      "The server returned an unreadable response.",
      "INVALID_RESPONSE",
      response.status,
    );
  }
  if (!response.ok) {
    throw new ApiError(
      data?.error?.message || "The request could not be completed.",
      data?.error?.code || "REQUEST_FAILED",
      response.status,
      data?.error?.trace_id || response.headers.get("X-Trace-ID") || undefined,
    );
  }
  return data as T;
}
