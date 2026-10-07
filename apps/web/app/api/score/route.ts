import { errorResponse, forward } from "../../../lib/proxy";

export const dynamic = "force-dynamic";

// POST /v1/score on the speech service. Only `audio` and `referenceText` are passed on.
export async function POST(request: Request): Promise<Response> {
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return errorResponse(422, "validation_error", "errors.validation");
  }
  const audio = form.get("audio");
  const referenceText = form.get("referenceText");
  if (!(audio instanceof Blob) || typeof referenceText !== "string") {
    return errorResponse(422, "validation_error", "errors.validation");
  }
  const body = new FormData();
  body.append("audio", audio, "recording");
  body.append("referenceText", referenceText);
  return forward("SPEECH_URL", "/v1/score", { method: "POST", body }, 30_000);
}
