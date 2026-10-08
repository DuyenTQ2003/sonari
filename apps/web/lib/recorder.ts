// Microphone recording with MediaRecorder. The browser picks the container: Chrome and Edge
// write WebM/Opus, Firefox Ogg/Opus, Safari MP4/AAC. The speech service reads all three.

export type MicProblem = "denied" | "not_found" | "unsupported" | "unavailable";

export class RecorderError extends Error {
  constructor(readonly problem: MicProblem) {
    super(problem);
  }
}

// In order of preference; the first one the browser can record wins.
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"];

export function pickMimeType(): string | undefined {
  return MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
}

function problemOf(error: unknown): MicProblem {
  switch ((error as { name?: string } | null)?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "denied";
    case "NotFoundError":
    case "OverconstrainedError":
      return "not_found";
    case "NotSupportedError": // what a headless Chromium and some insecure origins answer
      return "unsupported";
    default:
      return "unavailable"; // NotReadableError (another app holds the microphone) and the rest
  }
}

export type Recording = { stop: () => Promise<Blob> };

/** Asks for the microphone and starts recording. Throws `RecorderError`. */
export async function startRecording(): Promise<Recording> {
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    throw new RecorderError("unsupported"); // also what a page served over plain http gets
  }
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (error) {
    throw new RecorderError(problemOf(error));
  }
  const mimeType = pickMimeType();
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  recorder.start();
  return {
    stop: () =>
      new Promise((resolve) => {
        recorder.onstop = () => {
          stream.getTracks().forEach((track) => track.stop()); // turns the browser's mic light off
          resolve(new Blob(chunks, { type: recorder.mimeType }));
        };
        recorder.stop();
      }),
  };
}
