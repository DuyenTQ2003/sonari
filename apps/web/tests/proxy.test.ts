import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST as score } from "../app/api/score/route";
import { GET as speakingItems } from "../app/api/speaking-items/route";

const fetchMock = vi.fn();

beforeEach(() => {
  process.env.CORE_URL = "http://core.test:8000";
  process.env.SPEECH_URL = "http://speech.test:8001";
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });

function scoreRequest(fields: Record<string, string | Blob>): Request {
  const form = new FormData();
  for (const [name, value] of Object.entries(fields)) form.append(name, value);
  return new Request("http://web.test/api/score", { method: "POST", body: form });
}

const RECORDING = new Blob([new Uint8Array([1, 2, 3, 4])], { type: "audio/webm;codecs=opus" });
const ENVELOPE = (messageKey: string) => expect.objectContaining({ error: expect.objectContaining({ messageKey }) });

describe("GET /api/speaking-items", () => {
  it("asks the core service and returns its answer unchanged", async () => {
    const items = { items: [{ id: "a", text: "Hello there, my friend.", unit: "Study and work" }] };
    fetchMock.mockResolvedValue(json(items));

    const response = await speakingItems();

    expect(fetchMock.mock.calls[0][0]).toBe("http://core.test:8000/v1/speaking-items");
    expect(fetchMock.mock.calls[0][1].method).toBe("GET");
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/json");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual(items);
  });

  it("passes an error of the service on with its status and envelope", async () => {
    const envelope = { error: { code: "internal_error", messageKey: "errors.internal", details: null } };
    fetchMock.mockResolvedValue(json(envelope, 500));

    const response = await speakingItems();

    expect(response.status).toBe(500);
    expect(await response.json()).toEqual(envelope);
  });

  it("says the service is unavailable when it cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    const response = await speakingItems();

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual(ENVELOPE("errors.upstream.unavailable"));
  });

  it("gives up on a service that does not answer in time", async () => {
    fetchMock.mockRejectedValue(new DOMException("timed out", "TimeoutError"));

    expect((await speakingItems()).status).toBe(502);
    expect(fetchMock.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  });

  it("fails loudly, without calling anything, when the service URL is not set", async () => {
    delete process.env.CORE_URL;

    const response = await speakingItems();

    expect(response.status).toBe(500);
    expect(await response.json()).toEqual(ENVELOPE("errors.internal"));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("accepts a service URL with a trailing slash", async () => {
    process.env.CORE_URL = "http://core.test:8000/";
    fetchMock.mockResolvedValue(json({ items: [] }));

    await speakingItems();

    expect(fetchMock.mock.calls[0][0]).toBe("http://core.test:8000/v1/speaking-items");
  });
});

describe("POST /api/score", () => {
  it("sends the audio and the sentence to the speech service as multipart", async () => {
    const result = { thresholdsVersion: "v0-uncalibrated", referenceText: "Hello there, my friend.", words: [] };
    fetchMock.mockResolvedValue(json(result));

    const response = await score(scoreRequest({ audio: RECORDING, referenceText: "Hello there, my friend." }));

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://speech.test:8001/v1/score");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.body.get("referenceText")).toBe("Hello there, my friend.");
    const sent = init.body.get("audio") as File;
    expect(sent.size).toBe(RECORDING.size);
    expect(sent.type).toBe("audio/webm;codecs=opus");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(result);
  });

  it("forwards nothing but the two fields, and none of the browser's headers", async () => {
    fetchMock.mockResolvedValue(json({}));
    const request = scoreRequest({ audio: RECORDING, referenceText: "Hi.", admin: "1" });
    request.headers.set("cookie", "session=secret");

    await score(request);

    const init = fetchMock.mock.calls[0][1];
    expect([...init.body.keys()].sort()).toEqual(["audio", "referenceText"]);
    expect(init.headers).toBeUndefined();
  });

  it("passes the speech gate's 503 on with Retry-After and its envelope", async () => {
    const envelope = { error: { code: "busy", messageKey: "errors.speech.busy", details: { retryAfterS: 2 } } };
    fetchMock.mockResolvedValue(json(envelope, 503, { "retry-after": "2" }));

    const response = await score(scoreRequest({ audio: RECORDING, referenceText: "Hi." }));

    expect(response.status).toBe(503);
    expect(response.headers.get("retry-after")).toBe("2");
    expect(await response.json()).toEqual(envelope);
  });

  it("passes an audio error of the service on (too short, undecodable)", async () => {
    const envelope = { error: { code: "audio_too_short", messageKey: "errors.audio.too_short", details: null } };
    fetchMock.mockResolvedValue(json(envelope, 422));

    const response = await score(scoreRequest({ audio: RECORDING, referenceText: "Hi." }));

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual(envelope);
  });

  it.each([
    ["no audio", { referenceText: "Hi." }],
    ["no sentence", { audio: RECORDING }],
    ["a sentence sent as a file", { audio: RECORDING, referenceText: new Blob(["Hi."]) }],
    ["audio sent as text", { audio: "not audio", referenceText: "Hi." }],
  ])("refuses a request with %s, without calling the service", async (_, fields) => {
    const response = await score(scoreRequest(fields));

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual(ENVELOPE("errors.validation"));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses a body that is not multipart", async () => {
    const request = new Request("http://web.test/api/score", { method: "POST", body: "{}" });

    const response = await score(request);

    expect(response.status).toBe(422);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("says the service is unavailable when the speech service cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    const response = await score(scoreRequest({ audio: RECORDING, referenceText: "Hi." }));

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual(ENVELOPE("errors.upstream.unavailable"));
  });

  it("uses SPEECH_URL for scoring and CORE_URL for the items, not the other way round", async () => {
    fetchMock.mockResolvedValue(json({ items: [] }));
    await speakingItems();
    fetchMock.mockResolvedValue(json({}));
    await score(scoreRequest({ audio: RECORDING, referenceText: "Hi." }));

    expect(fetchMock.mock.calls.map((call) => new URL(call[0]).port)).toEqual(["8000", "8001"]);
  });
});
