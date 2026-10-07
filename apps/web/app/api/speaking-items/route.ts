import { forward } from "../../../lib/proxy";

export const dynamic = "force-dynamic";

// GET /v1/speaking-items on the core service.
export function GET(): Promise<Response> {
  return forward("CORE_URL", "/v1/speaking-items", { method: "GET" }, 10_000);
}
