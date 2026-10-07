"use client";

import { useEffect, useRef, useState } from "react";
import { loadItems, scoreRecording, type SpeakingItem } from "../lib/api";
import { messageFor, t } from "../lib/messages";
import { RecorderError, startRecording, type Recording } from "../lib/recorder";

type Phase = "loading" | "idle" | "recording" | "scoring";

const button =
  "rounded-lg px-4 py-2 font-medium text-white disabled:opacity-40 bg-slate-800 hover:bg-slate-700";

export default function Practice() {
  const [items, setItems] = useState<SpeakingItem[]>([]);
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null); // a message key
  const [audio, setAudio] = useState<Blob | null>(null); // kept so a failed scoring can be resent
  const [result, setResult] = useState<unknown>(null);
  const recording = useRef<Recording | null>(null);
  const item = items[index];

  useEffect(() => {
    loadItems().then((loaded) => {
      if (loaded.ok) setItems(loaded.data.items);
      else setError(loaded.messageKey);
      setPhase("idle");
    });
    return () => void recording.current?.stop(); // leaving the page must release the microphone
  }, []);

  async function submit(blob: Blob) {
    setPhase("scoring");
    setError(null);
    const scored = await scoreRecording(blob, item.text);
    if (scored.ok) setResult(scored.data);
    else setError(scored.messageKey);
    setPhase("idle");
  }

  async function start() {
    setError(null);
    setResult(null);
    setAudio(null);
    try {
      recording.current = await startRecording();
      setPhase("recording");
    } catch (problem) {
      setError(`errors.mic.${problem instanceof RecorderError ? problem.problem : "unavailable"}`);
    }
  }

  async function stop() {
    const blob = await recording.current!.stop();
    recording.current = null;
    setAudio(blob);
    await submit(blob);
  }

  function next() {
    setIndex((index + 1) % items.length);
    setResult(null);
    setError(null);
    setAudio(null);
  }

  const busy = phase !== "idle";
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
      <h1 className="text-2xl font-semibold">{t("practice.heading")}</h1>
      <p>{t("practice.instruction")}</p>

      {phase === "loading" && <p>{t("practice.loading")}</p>}
      {phase !== "loading" && !item && !error && <p>{t("practice.empty")}</p>}
      {item && (
        <p lang="en" className="rounded-lg bg-white p-4 text-xl shadow">
          {item.text}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {phase === "recording" ? (
          <button className={button} onClick={stop}>
            {t("practice.stop")}
          </button>
        ) : (
          <button className={button} onClick={start} disabled={busy || !item}>
            {audio || result ? t("practice.again") : t("practice.record")}
          </button>
        )}
        {error && audio && (
          <button className={button} onClick={() => submit(audio)} disabled={busy}>
            {t("practice.retry")}
          </button>
        )}
        <button className={button} onClick={next} disabled={busy || items.length < 2}>
          {t("practice.next")}
        </button>
      </div>

      {phase === "recording" && <p role="status">{t("practice.recording")}</p>}
      {phase === "scoring" && <p role="status">{t("practice.scoring")}</p>}
      {error && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-800">
          {messageFor(error)}
        </p>
      )}
      {result !== null && (
        <section>
          <h2 className="font-medium">{t("practice.result")}</h2>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-sm text-slate-100">
            {JSON.stringify(result, null, 2)}
          </pre>
        </section>
      )}
    </main>
  );
}
