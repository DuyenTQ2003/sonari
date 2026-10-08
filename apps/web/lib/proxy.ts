// The browser talks to this app only; the route handlers forward to the internal services.
// Failures this app causes use the services' error envelope, so the client handles one shape.

export type Service = "CORE_URL" | "SPEECH_URL";

export function errorResponse(status: number, code: string, messageKey: string): Response {
  return Response.json({ error: { code, messageKey, details: null } }, { status });
}

function baseUrl(service: Service): string {
  const url = process.env[service];
  if (!url) throw new Error(`${service} is not set (see apps/web/.env.example)`);
  return url.replace(/\/+$/, "");
}

/** Sends the request to `service` and returns its answer unchanged: status, body, and the
 *  headers a client acts on (content type, Retry-After). Never throws. */
export async function forward(
  service: Service,
  path: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  let url: string;
  try {
    url = baseUrl(service) + path;
  } catch (error) {
    console.error(error);
    return errorResponse(500, "misconfigured", "errors.internal");
  }
  let upstream: Response;
  try {
    upstream = await fetch(url, { ...init, cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
  } catch (error) {
    console.error(`${service} ${path} failed:`, error);
    return errorResponse(502, "upstream_unreachable", "errors.upstream.unavailable");
  }
  const headers = new Headers({ "cache-control": "no-store" });
  for (const name of ["content-type", "retry-after"]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}
