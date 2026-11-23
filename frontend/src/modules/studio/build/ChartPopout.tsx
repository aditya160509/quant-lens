"use client";

import { useEffect, useRef, useState } from "react";
import { DevChart } from "./DevChart";
import type { DevPreview } from "./DevIDE";

/** Build's chart in its own window: the editor window posts symbol, preview and paused date on "studio-chart";
 *  replay controls here post back to move the debugger there. */
type State = { symbol: string; prev: DevPreview | null; pausedAt: string | null; drawKey: string };

/** One channel per editor window (its id rides in the pop-out URL), so two strategies' pop-outs never cross. */
export const chartChannel = (id: string) => `studio-chart:${id}`;

export function ChartPopout() {
  const [st, setSt] = useState<State | null>(null);
  const [playing, setPlaying] = useState(false), [speed, setSpeed] = useState(1);
  const ch = useRef<BroadcastChannel | null>(null);
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("ch");
    if (!id) return;
    const c = ch.current = new BroadcastChannel(chartChannel(id));
    c.onmessage = (e: MessageEvent<{ type: string } & State>) => { if (e.data.type === "state") setSt(e.data); };
    c.postMessage({ type: "hello" });
    return () => c.close();
  }, []);
  useEffect(() => { document.title = st ? `${st.symbol} · Chart · ATLAS` : "Chart · ATLAS"; }, [st?.symbol]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!st) return <p className="dv-empty" style={{ padding: 24 }}>Waiting for the Build window…</p>;
  return (
    <div className="dv-popout"><DevChart symbol={st.symbol} drawKey={st.drawKey} prev={st.prev} pausedAt={st.pausedAt} playing={playing} speed={speed} onPlay={setPlaying} onSpeed={setSpeed}
      onGo={(date, step) => ch.current?.postMessage({ type: "go", date, step })} /></div>
  );
}
