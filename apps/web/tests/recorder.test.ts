import { afterEach, describe, expect, it, vi } from "vitest";
import { pickMimeType, RecorderError, startRecording } from "../lib/recorder";

afterEach(() => vi.unstubAllGlobals());

/** A MediaRecorder that supports only `supported`, and records the chunks it is given. */
function stubRecorder(supported: string[]) {
  class FakeRecorder {
    static isTypeSupported = (type: string) => supported.includes(type);
    static created: { options?: { mimeType?: string } }[] = [];
    mimeType: string;
    ondataavailable?: (event: { data: Blob }) => void;
    onstop?: () => void;
    constructor(_stream: unknown, readonly options?: { mimeType?: string }) {
      FakeRecorder.created.push({ options });
      this.mimeType = options?.mimeType ?? "audio/default";
    }
    start() {}
    stop() {
      this.ondataavailable?.({ data: new Blob(["abc"]) });
      this.ondataavailable?.({ data: new Blob([]) }); // an empty chunk is dropped
      this.onstop?.();
    }
  }
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  return FakeRecorder;
}

function stubMicrophone(getUserMedia: () => Promise<unknown>) {
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
}

describe("pickMimeType", () => {
  it.each([
    ["Chrome and Edge", ["audio/webm;codecs=opus", "audio/webm"], "audio/webm;codecs=opus"],
    ["Firefox", ["audio/ogg;codecs=opus", "audio/webm;codecs=opus"], "audio/webm;codecs=opus"],
    ["Firefox without WebM", ["audio/ogg;codecs=opus"], "audio/ogg;codecs=opus"],
    ["Safari", ["audio/mp4"], "audio/mp4"],
  ])("%s", (_, supported, expected) => {
    stubRecorder(supported);
    expect(pickMimeType()).toBe(expected);
  });

  it("is undefined when the browser supports none, and recording then lets it choose", () => {
    stubRecorder([]);
    expect(pickMimeType()).toBeUndefined();
  });
});

describe("startRecording", () => {
  it.each([
    ["NotAllowedError", "denied"],
    ["SecurityError", "denied"],
    ["NotFoundError", "not_found"],
    ["OverconstrainedError", "not_found"],
    ["NotSupportedError", "unsupported"],
    ["NotReadableError", "unavailable"],
    ["AbortError", "unavailable"],
  ])("maps %s to %s", async (name, problem) => {
    stubRecorder(["audio/webm"]);
    stubMicrophone(() => Promise.reject(new DOMException("no", name)));

    await expect(startRecording()).rejects.toMatchObject({ problem });
    await expect(startRecording()).rejects.toBeInstanceOf(RecorderError);
  });

  it("is unsupported without getUserMedia (an http page has no mediaDevices) or MediaRecorder", async () => {
    stubRecorder(["audio/webm"]);
    vi.stubGlobal("navigator", {});
    await expect(startRecording()).rejects.toMatchObject({ problem: "unsupported" });

    stubMicrophone(() => Promise.resolve({}));
    vi.stubGlobal("MediaRecorder", undefined);
    await expect(startRecording()).rejects.toMatchObject({ problem: "unsupported" });
  });

  it("records with the picked format, and stopping gives the audio and frees the microphone", async () => {
    const recorder = stubRecorder(["audio/mp4"]);
    const track = { stop: vi.fn() };
    stubMicrophone(() => Promise.resolve({ getTracks: () => [track] }));

    const recording = await startRecording();
    const blob = await recording.stop();

    expect(recorder.created[0].options).toEqual({ mimeType: "audio/mp4" });
    expect(blob.type).toBe("audio/mp4");
    expect(blob.size).toBe(3);
    expect(track.stop).toHaveBeenCalledOnce();
  });
});
